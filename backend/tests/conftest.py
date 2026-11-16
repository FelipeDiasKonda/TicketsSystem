from environment import configure_test_environment

# Tests use isolated databases and must not depend on a developer's credentials.
configure_test_environment()
