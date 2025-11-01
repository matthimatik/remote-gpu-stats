import paramiko
from typing import Optional


class JumpHost:
    """Manage a reusable SSH connection to a jump host."""

    def __init__(self, host: str, username: str, password: str):
        self.host = host
        self.username = username
        self.password = password
        self._client: Optional[paramiko.SSHClient] = None
        self._transport: Optional[paramiko.Transport] = None

    def __enter__(self) -> "JumpHost":
        """Open the SSH connection to the jump host."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            self.host,
            username=self.username,
            password=self.password,
            allow_agent=False,
            look_for_keys=False,
        )

        self._transport = self._client.get_transport()
        if not self._transport:
            raise RuntimeError("Failed to get jump host transport")

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Close the jump host connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._transport = None

    def get_channel(
        self,
        target_host: str,
    ) -> paramiko.Channel:
        """
        Open a new SSH connection to a target host through this jump host.
        Returns a ready-to-use SSHClient.
        """

        if not self._transport or not self._transport.is_active():
            raise RuntimeError("Jump host transport is not active")

        return self._transport.open_channel(
            "direct-tcpip",
            dest_addr=(target_host, 22),
            src_addr=("127.0.0.1", 0),
            timeout=5,
        )




def connect(
    channel: paramiko.Channel,
    target_host: str,
    username: str,
    password: str,
    key_filename: Optional[str] = None,
):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=target_host,
        username=username,
        password=password,
        key_filename=key_filename,
        sock=channel,
        allow_agent=False,
        look_for_keys=False,
        timeout=5,              # connection timeout
        banner_timeout=5,
        auth_timeout=5,
    )
    return client
