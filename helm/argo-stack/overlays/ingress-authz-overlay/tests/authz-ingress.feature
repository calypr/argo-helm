Feature: Authz ingress overlay

  Background:
    Given the ingress-authz-overlay is installed
    And the hostname "calypr-demo.ddns.net" resolves to the ingress endpoint

  Scenario: Unauthenticated user is redirected to login
    When I send a GET request to "https://calypr-demo.ddns.net/workflows"
    Then the response status should be 302 or 303
    And the "Location" header should contain "/tenants/login"

  Scenario: Authenticated user can access workflows
    Given I have a valid session recognized by authz-adapter
    When I send a GET request to "https://calypr-demo.ddns.net/workflows"
    Then the response status should be 200

  Scenario: All paths are protected by authz-adapter
    When I send a GET request to "https://calypr-demo.ddns.net/applications" without credentials
    Then I should be redirected to "/tenants/login"

    When I send a GET request to "https://calypr-demo.ddns.net/registrations" without credentials
    Then I should be redirected to "/tenants/login"

    When I send a GET request to "https://calypr-demo.ddns.net/api" without credentials
    Then I should be redirected to "/tenants/login"

    When I send a GET request to "https://calypr-demo.ddns.net/tenants" without credentials
    Then I should be redirected to "/tenants/login" or served only public content as configured

  Scenario: TLS certificate is valid
    When I connect to "https://calypr-demo.ddns.net"
    Then the TLS certificate should be issued by "Let's Encrypt"
    And the certificate subject alt name should include "calypr-demo.ddns.net"

  Scenario: Routing sends requests to the correct services
    Given I am authenticated
    When I send a GET request to "https://calypr-demo.ddns.net/workflows"
    Then the response should contain an HTML title for the workflows UI

    When I send a GET request to "https://calypr-demo.ddns.net/applications"
    Then the response should contain an HTML title for the applications UI

    When I send a GET request to "https://calypr-demo.ddns.net/api/health"
    Then I should receive a 200 response with a JSON health object from the API

    When I send a GET request to "https://calypr-demo.ddns.net/tenants"
    Then I should see the tenant portal landing page or login as configured

  Scenario: Auth response headers are passed to backend
    Given I am authenticated with user "test@example.com" in groups "argo-runner,argo-viewer"
    When I send a GET request to "https://calypr-demo.ddns.net/api/whoami"
    Then the backend should receive header "X-Auth-Request-User" with value "test@example.com"
    And the backend should receive header "X-Auth-Request-Groups" with value "argo-runner,argo-viewer"

  Scenario: Path rewriting works correctly
    Given I am authenticated
    When I send a GET request to "https://calypr-demo.ddns.net/workflows/workflow-details/my-workflow"
    Then the Argo Workflows server should receive path "/workflow-details/my-workflow"

    When I send a GET request to "https://calypr-demo.ddns.net/api/v1/users"
    Then the Calypr API should receive path "/v1/users"

  Scenario: Health check endpoint is accessible
    When I send a GET request to "http://authz-adapter.argo-stack.svc.cluster.local:8080/healthz"
    Then the response status should be 200
    And the response body should be "ok"

  Scenario: Multiple simultaneous requests are handled
    Given I am authenticated
    When I send 10 concurrent GET requests to "https://calypr-demo.ddns.net/workflows"
    Then all responses should have status 200
    And the average response time should be less than 500ms
