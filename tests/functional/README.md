# Functional Tests

The functional tests for this project have been migrated to integration tests.
Any end-to-end or workflow testing should be added to the following directories:

- `tests/integration/`: For testing full workflow paths
- `tests/auth/`: For authentication-related workflows 
- `tests/main/`: For main application flows

## Migrating Tests

If you need to add new functional tests:

1. Consider if they belong in one of the integration test directories
2. If they test core workflows, add them to `tests/integration/`
3. Make sure they use the Flask test client

## Why We Migrated

We've consolidated our testing approach to make maintenance easier. The integration 
tests now cover end-to-end workflows while being more maintainable than traditional
UI-driven functional tests.
