import json
import os
import uuid

from tornado import ioloop, web, auth, httpserver, gen, escape
from tornado.options import options, parse_command_line, define

from contest import Contest
from judge import Judge
from data_uri import DataURI


define('admin_whitelist', default='TODO:replace_own_email',
       help='emails of admins', type=str, multiple=True)
define('port', default=8000,
       help='start on the given port', type=int)
define('contest_dir', default='contest',
       help='path to the contest files', type=str)
define('delay', default=15*60,
       help='delay (in seconds) before starting the contest', type=int)


class BaseHandler(web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie('utacm_contest_user')
        if not user_json:
            return None
        return escape.json_decode(user_json)

    def get_current_user_id(self):
        cookie = self.get_current_user()
        return (cookie['email'], cookie['name'])


class AuthLoginHandler(BaseHandler, auth.GoogleMixin):
    @gen.coroutine
    def get(self):
        if self.get_argument('openid.mode', None):
            user = yield self.get_authenticated_user()
            self.set_secure_cookie('utacm_contest_user',
                                   escape.json_encode(user))
            self.redirect('/')
            return
        self.authenticate_redirect(ax_attrs=[
            'name', 'email', 'language', 'username'])


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie('utacm_contest_user')
        self.write("You are now logged out.")


class IndexHandler(BaseHandler):
    @web.authenticated
    def get(self):
        # Serve page
        # Make sure to send pre-contest page if pre-contest
        # should be asynchronous
        if contest.is_running():
            self.render('contest.html')
        else:
            self.render('pre-contest.html')


class MetadataHandler(BaseHandler):
    @web.authenticated
    def get(self):
        if not contest.is_running():
            raise web.HTTPError(503)
        data = {
            'prob_ids': contest_cfg['prob_ids'],
            'prob_contents': problem_contents,
        }
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(data))


class UpdatesHandler(BaseHandler):
    @web.authenticated
    def get(self):
        # Send updates in json form
        # Updates being: remaining time, scoreboard, clarifications
        updates = {
            'remaining_time': contest.remaining_time(),
            'scoreboard': contest.get_scoreboard(),
            'clarifications': contest.get_clarifs(self.get_current_user_id()),
        }
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(updates))


class PermitsHandler(BaseHandler):
    @web.authenticated
    def post(self):
        # Requests a new permit. Body should be just the prob_id
        # Return ttl of permit if max permits have been issued
        # Raises a 403 error if out of permits
        # should be asynchronous
        if not contest.is_running():
            raise web.HTTPError(503)
        user_id = self.get_current_user_id()
        prob_id = self.get_argument('content')
        if prob_id not in contest_cfg['prob_ids']:
            raise web.HTTPError(400)
        permit = judge.get_expiring_permit(user_id, prob_id)
        if permit is None:
            raise web.HTTPError(403)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(permit))


class InputFilesHandler(BaseHandler):
    @web.authenticated
    def get(self, prob_id):
        # Sends the input file for the specified problem
        # verify valid prob_id
        # Check permit, return error if expired
        if not contest.is_running():
            raise web.HTTPError(503)
        if prob_id not in contest_cfg['prob_ids']:
            raise web.HTTPError(404)
        user_id = self.get_current_user_id()
        text = judge.get_input_text(user_id, prob_id)
        if text is None:
            raise web.HTTPError(409)
        self.set_header('Content-Type', 'application/octet-stream')
        self.write(text)


class SubmitSolutionHandler(BaseHandler):
    @web.authenticated
    def post(self, prob_id):
        # Requests a solution be graded
        # Body should contain: source code, output
        # Verify valid prob_id
        # Check permit, return error if expired
        # Dispatch to judge, return True or False based on accepted or not
        if not contest.is_running():
            raise web.HTTPError(503)
        if prob_id not in contest_cfg['prob_ids']:
            raise web.HTTPError(404)
        user_id = self.get_current_user_id()
        try:
            output = DataURI(self.get_argument('outputFile')).data
        except:
            output = "MALFORMED OUTPUT"
        try:
            source_code = DataURI(self.get_argument('sourceFile')).data
        except:
            source_code = "MALFORMED SOURCE CODE"
        result = judge.judge_submission(user_id, prob_id, source_code, output)
        if result is None:
            raise web.HTTPError(409)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(result))


class SubmitClarificationHandler(BaseHandler):
    @web.authenticated
    def post(self, prob_id):
        # Requests a solution be graded
        # Body should contain: source code, output
        # Verify valid prob_id
        # Check permit, return error if expired
        # Dispatch to judge, return True or False based on accepted or not
        if not contest.is_running():
            raise web.HTTPError(503)
        if prob_id not in contest_cfg['prob_ids']:
            raise web.HTTPError(404)
        user_id = self.get_current_user_id()
        message = self.get_argument('content')
        contest.submit_clarif(user_id, prob_id, message)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps(True))


class AdminHandler(BaseHandler):
    @web.authenticated
    def get(self):
        if self.get_current_user_id()[0] not in options.admin_whitelist:
            raise web.HTTPError(404)

        rem = contest.remaining_time()
        webpage = '''<h1>======== DEBUG ========</h1><br>
        <b>Contest is currently running:</b> %s<br>
        <b>Remaining time</b>: %02d:%02d:%02d<br>
        <b>Scoreboard</b>:<br>
        %s<br>
        <b>Clarifications</b>:<br>
        %s<br>
        <h1>====== END DEBUG ======</h1><br>''' % (
            contest.is_running(),
            int(rem / 60 / 60), int(rem / 60 % 60), int(rem % 60),
            json.dumps(contest.get_scoreboard(), indent=4),
            json.dumps(contest.get_clarifs(-1), indent=4),
        )
        self.write(webpage)
        # TODO: move logic code out of console.py to here


if __name__ == '__main__':
    parse_command_line()

    contest_cfg_path = os.path.join(options.contest_dir, 'config.txt')
    with open(contest_cfg_path, 'r') as in_file:
        contest_cfg = eval(in_file.read())

    def get_problem_content(prob_id):
        content_path = os.path.join(options.contest_dir,
                                    'problems',
                                    prob_id,
                                    'content.html')
        with open(content_path, 'r') as in_file:
            return in_file.read()

    problem_contents = {prob_id: get_problem_content(prob_id)
                        for prob_id in contest_cfg['prob_ids']}

    contest = Contest(options.delay, contest_cfg['duration'],
                      contest_cfg['prob_ids'], contest_cfg['penalty'])
    judge = Judge(contest, contest_cfg['prob_ids'], options.contest_dir)

    application = web.Application(
        [
            (r'/', IndexHandler),
            (r'/index.html', IndexHandler),
            (r'/admin', AdminHandler),
            (r'/auth/login', AuthLoginHandler),
            (r'/auth/logout', AuthLogoutHandler),
            (r'/api/v1/metadata', MetadataHandler),
            (r'/api/v1/updates', UpdatesHandler),
            (r'/api/v1/permits', PermitsHandler),
            (r'/api/v1/files/(.*)/input.txt', InputFilesHandler),
            (r'/api/v1/submit/(.*)/solution', SubmitSolutionHandler),
            (r'/api/v1/submit/(.*)/clarification', SubmitClarificationHandler),
        ],
        cookie_secret='TODO: generate a random cookie',
        login_url='/auth/login',
        template_path=os.path.join(os.path.dirname(__file__), 'templates'),
        static_path=os.path.join(os.path.dirname(__file__), 'static'),
        xsrf_cookies=True,
        debug=True,
    )

    application.listen(
        port=options.port,
        max_buffer_size=128*1024,
    )
    ioloop.IOLoop.instance().start()
