REMOTE_CMD = r"""
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{
    for(i=1; i<=NF; i++) {
        if ($i ~ /id$/) {
            # Das ist das Idle-Feld
            print 100 - $(i-1);
            exit;
        }
    }
    # Fallback, falls das Muster nicht gefunden wird (z.B. %id ist Feld 8)
    if ($8 ~ /[0-9.]/) { print 100 - $8; } else { print 0; }
}')

RAM_USED=$(free -m | awk '/Mem:/ {print $3}')
RAM_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
echo "CPU:$CPU RAM:${RAM_USED}/${RAM_TOTAL}MB"
# ... Rest des Skripts ...
"""