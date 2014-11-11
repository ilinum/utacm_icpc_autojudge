var preContestControllers = angular.module('preContestControllers', []);

preContestControllers.controller('MainCtrl', ['$scope', '$http', '$timeout',
    function ($scope, $http, $timeout, $window) {
      function sync () {
        $http.get('api/v1/updates').success(function (data) {
          if ($scope.rawTime < parseInt(data['remaining_time'])) {
            $window.location.reload();
          }
          $scope.rawTime = data['remaining_time'];
          $scope.remainingTime = moment($scope.rawTime);
        });
        $timeout(sync, 5000);
        for (i = 1000; i <= 4000; i += 1000) {
          $timeout(tick, i);
        }
      }

      function tick () {
        $scope.rawTime -= 1;
        if ($scope.rawTime < 0) {
          $window.location.reload();
        } else {
          $scope.remainingTime = moment($scope.rawTime);
        }
      }

      sync();
    }]);

preContestControllers.controller('HomeCtrl', ['$scope', '$http',
    function ($scope, $http) {
    }]);


var contestControllers = angular.module('contestControllers', []);
var probIds = [];

contestControllers.controller('MainCtrl', ['$scope', '$http', '$timeout', '$rootScope',
    function ($scope, $http, $timeout, $window) {
      $http.get('api/v1/metadata').success(function (data) {
        $scope.probIds = probIds = data['prob_ids'];
        $scope.probContents = data['prob_contents'];
      });

      function sync () {
        $http.get('api/v1/updates').success(function (data) {
          $scope.rawTime = data['remaining_time'];
          $scope.scoreboard = data['scoreboard'];
          $scope.clarifications = data['clarifications'];
          $scope.remainingTime = moment($scope.rawTime);
        });
        $timeout(sync, 5000);
        for (i = 1000; i <= 4000; i += 1000) {
          if ($scope.rawTime > 0) {
            $timeout(tick, i);
          }
        }
      }

      function tick () {
        $scope.rawTime -= 1;
        if ($scope.rawTime >= 0) {
          $scope.remainingTime = moment($scope.rawTime);
        }
      }

      sync();
    }]);

contestControllers.controller('HomeCtrl', ['$scope', '$http',
    function ($scope, $http) {
    }]);

contestControllers.controller('AdminCtrl', ['$scope', '$http', '$cookies', '$window',
    function ($scope, $http, $cookies, $window) {
      $scope.processAddTimeInput = function(numMin) {
        submit_url = 'api/v1/admin' + numMin;
        submit_data = { '_xsrf': $cookies._xsrf, 'content': numMin };
      }

      $scope.proccessClarifResponse = function(respNum, clarifNum) {
        submit_url = 'api/v1/admin';
        submit_data = { '_xsrf': $cookies._xsrf, 'respNum': respNum, 'clarifNum': clarifNum };
        $http({
          method  : 'PUT',
          url     : submit_url,
          data    : $.param(submit_data),
          headers : { 'Content-Type': 'application/x-www-form-urlencoded' },
        }).success(function(data) {
          if (data) {
            $window.alert("clarif reply successfully submitted");
          }
        });

      }
    }]);

contestControllers.controller('ProblemCtrl', ['$scope', '$http', '$rootScope', '$window', '$cookies', '$interval',
    function ($scope, $http, $rootScope, $window, $cookies, $interval) {
      var tabClasses;
        
      $scope.files = {};
      $scope.files.output = [];
      $scope.files.source = [];
      i = 0;
      for (probId in probIds) {
        $scope.files.output.push("");
        $scope.files.source.push("");
      }
      if (typeof $rootScope.showSubmit == 'undefined') {
        $rootScope.showSubmit = [];
        $rootScope.ttl = [];
        $rootScope.ttlText = [];
        $rootScope.tick = [];
        for (probId in probIds) {
          $rootScope.showSubmit.push(false);
          $rootScope.ttl.push(-1);
          $rootScope.ttlText.push("");
          $rootScope.tick.push(null);
        }
      }

      function initTabs() {
        tabClasses = [];
        $scope.open = [];
        for (probId in probIds) {
          tabClasses.push("");
          $scope.open.push(false);
        }
      }
      
      $scope.getTabClass = function (tabNum) {
        return tabClasses[tabNum];
      };
      
      $scope.getTabPaneClass = function (tabNum) {
        return "tab-pane " + tabClasses[tabNum];
      }
      
      $scope.setActiveTab = function (tabNum) {
        initTabs();
        tabClasses[tabNum] = "active panel-primary";
        $rootScope.activeTab = tabNum;
        $scope.open[tabNum - 1] = true;
      };

      if (typeof $rootScope.activeTab == 'undefined') {
        $scope.setActiveTab(1);
      } else {
        $scope.setActiveTab($rootScope.activeTab);
      }

      $scope.clarif = {}
      $scope.processClarifForm = function (index) {
        submitUrl = 'api/v1/submit/' + probIds[index] + '/clarification';
        submitData = { '_xsrf': $cookies._xsrf, 'content': $scope.clarif[index] };
        $http({
          method  : 'POST',
          url     : submitUrl,
          data    : $.param(submitData),
          headers : { 'Content-Type': 'application/x-www-form-urlencoded' },
        }).success(function (data) {
          if (data) {
            $window.alert("Clarification submitted successfully!");
            $scope.clarif[probId] = "";
          }
        });
      }

      function tick (index) {
        $rootScope.ttl[index] -= 1;
        $rootScope.ttlText[index] = momentMinutes($rootScope.ttl[index]);
        if ($rootScope.ttl[index] <= 0) {
          $rootScope.showSubmit[index] = false;
          if ($rootScope.tick[index] != null) {
            $interval.cancel($rootScope.tick[index]);
            $rootScope.tick[index] = null;
          }
        }
      }

      $scope.getPermit = function (index) {
        permitUrl = 'api/v1/permits';
        permitData = { '_xsrf': $cookies._xsrf, 'content': probIds[index] };
        $http({
          method  : 'POST',
          url     : permitUrl,
          data    : $.param(permitData),
          headers : { 'Content-Type': 'application/x-www-form-urlencoded' },
        }).success(function (data) {
          if ($rootScope.tick[index] != null) {
            $interval.cancel($rootScope.tick[index]);
            $rootScope.tick[index] = null;
          }
          $rootScope.showSubmit[index] = true;
          $rootScope.ttl[index] = data;
          $rootScope.ttlText[index] = momentMinutes($rootScope.ttl[index]);
          $rootScope.tick[index] = $interval(function () {
            tick(index);
          }, 1000, data);
        }).error(function (data, status, headers, config) {
          if (status == 403) {
            $window.alert("You are out of permits!");
          }
        });
      }

      $scope.processSubmitForm = function (index) {
        submitUrl = 'api/v1/submit/' + probIds[index] + '/solution';
        submitData = { '_xsrf': $cookies._xsrf,
                       'outputFile': $scope.files.output[index],
                       'sourceFile': $scope.files.source[index], };
        $rootScope.showSubmit[index] = false;
        $rootScope.ttl[index] = 0;
        if ($rootScope.tick[index] != null) {
          $interval.cancel($rootScope.tick[index]);
          $rootScope.tick[index] = null;
        }
        $http({
          method  : 'POST',
          url     : submitUrl,
          data    : $.param(submitData),
          headers : { 'Content-Type': 'application/x-www-form-urlencoded' },
        }).success(function (data) {
          if (data) {
            $window.alert("Solution accepted!");
          } else {
            $window.alert("Solution incorrect!");
          }
        });
      }
    }]);

contestControllers.controller('ScoreboardCtrl', ['$scope', '$http',
    function ($scope, $http) {
    }]);
