"""Mirsad Python SDK: guard tool calls of any agent framework with a running Mirsad gateway.

```python
from mirsad.sdk import MirsadClient, MirsadBlocked

mirsad = MirsadClient("http://127.0.0.1:8700", api_key="mk_...")

@mirsad.guard
def send_email(to: str, subject: str, body: str) -> dict:
    ...

text_for_the_model = send_email("ali@najd-trading.example", "Hi", "...")  # inspected text
```
"""

from mirsad.sdk.client import AsyncMirsadClient, MirsadAuthError, MirsadBlocked, MirsadClient, MirsadError

__all__ = ["AsyncMirsadClient", "MirsadAuthError", "MirsadBlocked", "MirsadClient", "MirsadError"]
