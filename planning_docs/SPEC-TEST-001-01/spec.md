# SPEC-TEST-001-01: Implement Greeting Endpoint

## Summary
Add a `/greet` endpoint that returns a personalized greeting.

## Acceptance Criteria
1. GET /greet?name=X returns JSON `{"message": "Hello, X!"}`
2. Missing name parameter returns 400 error
3. Empty name returns 400 error
4. Endpoint has unit tests
