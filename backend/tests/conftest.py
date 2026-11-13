import os
from secrets import token_hex

# Tests use isolated databases and must not depend on a developer's credentials.
os.environ["DATABASE_PASSWORD"] = token_hex(32)
