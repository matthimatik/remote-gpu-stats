import getpass
import paramiko
import time

jump_host = "rzssh1.informatik.uni-hamburg.de"
jump_user = "8hirsch"
target_host = "cvpc7.informatik.uni-hamburg.de"
target_user = "8hirsch"

jump_pw = getpass.getpass("Jump password: ")
target_pw = getpass.getpass("Target password: ")

# Connect to jump host
jump_client = paramiko.SSHClient()
jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
jump_client.connect(jump_host, username=jump_user, password=jump_pw)

# Open a channel from the jump host to the target host
transport = jump_client.get_transport()
# dest_addr is (target_host, 22), src_addr is local addr on the jump side (host, port)
channel = transport.open_channel("direct-tcpip", (target_host, 22), ("127.0.0.1", 0))

# Use that channel as the socket for a new SSHClient to the target
target_client = paramiko.SSHClient()
target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Important: pass sock=channel and disable agent/keys if you want to use provided password
target_client.connect(
    hostname=target_host,
    username=target_user,
    password=target_pw,
    sock=channel,
    allow_agent=False,
    look_for_keys=False,
    timeout=10,
)

# Now execute commands on the target
stdin, stdout, stderr = target_client.exec_command("free -m | awk '/Mem:/ {print $3, $2}'")
used, total = stdout.read().decode().strip().split()
print(f"RAM used: {used} MB / {total} MB")

# cleanup
target_client.close()
jump_client.close()
