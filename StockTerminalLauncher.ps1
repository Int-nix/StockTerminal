Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

# ============================================================
# STOCKTERMINAL | WINDOWS LAUNCHER
# WITH LIVE TERMINAL OUTPUT
# ============================================================

# WSL configuration
$project = '/mnt/c/Users/owena/desktop/stockterminal'
$python = '/home/owena/.stockterminal-venv/bin/python'

# Process state
$script:process = $null
$script:pidFile = $null
$script:stopping = $false
$script:stopProcess = $null
$script:stopDeadline = [datetime]::MinValue
$script:requestedStop = $false

# ============================================================
# COLORS
# ============================================================

$bg     = [System.Drawing.Color]::FromArgb(13, 19, 27)
$panel  = [System.Drawing.Color]::FromArgb(22, 32, 43)
$panel2 = [System.Drawing.Color]::FromArgb(27, 40, 53)
$border = [System.Drawing.Color]::FromArgb(48, 65, 78)

$green = [System.Drawing.Color]::FromArgb(89, 225, 152)
$white = [System.Drawing.Color]::FromArgb(235, 243, 247)
$muted = [System.Drawing.Color]::FromArgb(151, 171, 186)
$red   = [System.Drawing.Color]::FromArgb(207, 83, 91)
$amber = [System.Drawing.Color]::FromArgb(237, 185, 95)

# ============================================================
# UI HELPERS
# ============================================================

function Font($size, $bold = $false, $mono = $false) {

    $family = if ($mono) {
        'Consolas'
    } else {
        'Segoe UI'
    }

    $style = if ($bold) {
        [System.Drawing.FontStyle]::Bold
    } else {
        [System.Drawing.FontStyle]::Regular
    }

    return New-Object System.Drawing.Font(
        $family,
        $size,
        $style
    )
}

function Label(
    $parent,
    $value,
    $x,
    $y,
    $w,
    $h,
    $size,
    $color,
    $bold = $false,
    $mono = $false
) {

    $c = New-Object System.Windows.Forms.Label

    $c.Text = $value

    $c.Location = New-Object System.Drawing.Point($x, $y)
    $c.Size = New-Object System.Drawing.Size($w, $h)

    $c.Font = Font $size $bold $mono
    $c.ForeColor = $color

    $c.BackColor = [System.Drawing.Color]::Transparent

    $parent.Controls.Add($c)

    return $c
}

function Panel($parent, $x, $y, $w, $h, $color) {

    $c = New-Object System.Windows.Forms.Panel

    $c.Location = New-Object System.Drawing.Point($x, $y)
    $c.Size = New-Object System.Drawing.Size($w, $h)

    $c.BackColor = $color

    $parent.Controls.Add($c)

    return $c
}

# ============================================================
# WSL PROCESS
# ============================================================

function New-WSLProcess(
    $command,
    $captureOutput = $false
) {

    $psi = New-Object System.Diagnostics.ProcessStartInfo

    $psi.FileName = 'wsl.exe'

    $psi.Arguments = '-d Ubuntu -- bash -lc "' + $command + '"'

    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    if ($captureOutput) {

        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true

        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    }

    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi

    if (-not $p.Start()) {
        throw 'Failed to start WSL process.'
    }

    return $p
}

# ============================================================
# MAIN WINDOW
# ============================================================

$form = New-Object System.Windows.Forms.Form

$form.Text = 'StockTerminal | Launcher'

$form.ClientSize = New-Object System.Drawing.Size(860, 790)

$form.StartPosition = 'CenterScreen'

$form.FormBorderStyle = 'FixedSingle'

$form.MaximizeBox = $false

$form.BackColor = $bg
$form.ForeColor = $white

$form.Font = Font 10

# ============================================================
# TOP BANNER
# ============================================================

$top = Panel $form 0 0 860 122 $panel

$accent = Panel $top 0 0 6 122 $green

$null = Label `
    $top `
    'STOCKTERMINAL' `
    33 20 710 54 31 $white $true

$null = Label `
    $top `
    'MARKET RESEARCH SYSTEM  /  DESKTOP LAUNCHER' `
    36 77 740 24 10 $green $false $true

# ============================================================
# LEFT INFORMATION PANEL
# ============================================================

$info = Panel $form 26 148 505 245 $panel

$null = Label `
    $info `
    'YOUR RESEARCH WORKSPACE' `
    22 20 450 27 12 $green $true $true

$null = Label `
    $info `
    'One place to investigate markets,' `
    22 55 460 31 17 $white $true

$null = Label `
    $info `
    'companies, and investment ideas.' `
    22 87 460 31 17 $white $true

$line = Panel $info 22 131 460 1 $border

$null = Label `
    $info `
    'RESEARCH MODULES' `
    22 148 460 24 10 $muted $true $true

$null = Label `
    $info `
    '01   Stock Explorer / Technical & Fundamental' `
    22 179 470 22 10 $white $false $true

$null = Label `
    $info `
    '02   Screener / News / Watchlist / Paper Trading' `
    22 208 470 22 10 $white $false $true

# ============================================================
# APPLICATION STATUS
# ============================================================

$stateCard = Panel $form 546 148 288 245 $panel2

$null = Label `
    $stateCard `
    'APPLICATION STATUS' `
    20 20 255 24 10 $muted $true $true

$dot = Panel $stateCard 22 62 13 13 $green

$stateLabel = Label `
    $stateCard `
    'READY' `
    46 50 222 38 21 $green $true

$detailLabel = Label `
    $stateCard `
    'Ready to start StockTerminal.' `
    22 101 245 58 10 $muted

$null = Label `
    $stateCard `
    'ENVIRONMENT' `
    22 177 240 20 9 $muted $true $true

$null = Label `
    $stateCard `
    'WSL / Ubuntu / Python Virtual Environment' `
    22 205 260 22 9 $white $false $true

# ============================================================
# TERMINAL PANEL
# ============================================================

$terminalPanel = Panel $form 26 411 808 270 $panel

$null = Label `
    $terminalPanel `
    'LIVE TERMINAL OUTPUT' `
    18 13 400 25 11 $green $true $true

$terminalStatus = Label `
    $terminalPanel `
    'Waiting for application...' `
    18 39 400 20 9 $muted

$terminal = New-Object System.Windows.Forms.RichTextBox

$terminal.Location = New-Object System.Drawing.Point(16, 65)

$terminal.Size = New-Object System.Drawing.Size(776, 190)

$terminal.BackColor = [System.Drawing.Color]::FromArgb(9, 14, 20)

$terminal.ForeColor = $green

$terminal.Font = Font 9 $false $true

$terminal.ReadOnly = $true

$terminal.BorderStyle = 'None'

$terminal.WordWrap = $false

$terminal.ScrollBars = 'Both'

$terminal.DetectUrls = $false

$terminalPanel.Controls.Add($terminal)

# ============================================================
# BOTTOM ACTION BAR
# ============================================================

$bottom = Panel $form 26 698 808 70 $panel

$activity = Label `
    $bottom `
    'STANDBY // LOCAL RESEARCH ENVIRONMENT' `
    19 14 555 23 10 $muted $false $true

$hint = Label `
    $bottom `
    'Terminal output remains visible after a crash.' `
    19 40 575 20 9 $muted

$launch = New-Object System.Windows.Forms.Button

$launch.Text = 'LAUNCH >'

$launch.Location = New-Object System.Drawing.Point(606, 10)

$launch.Size = New-Object System.Drawing.Size(182, 50)

$launch.FlatStyle = 'Flat'

$launch.FlatAppearance.BorderSize = 0

$launch.BackColor = [System.Drawing.Color]::FromArgb(40, 145, 88)

$launch.ForeColor = [System.Drawing.Color]::White

$launch.Font = Font 14 $true $true

$launch.Cursor = [System.Windows.Forms.Cursors]::Hand

$bottom.Controls.Add($launch)

# ============================================================
# TERMINAL LOGGING
# ============================================================

function Write-Terminal($message, $color = $green) {

    if (-not $terminal -or $terminal.IsDisposed) {
        return
    }

    $terminal.SelectionStart = $terminal.TextLength

    $terminal.SelectionLength = 0

    $terminal.SelectionColor = $color

    $terminal.AppendText(
        $message + [Environment]::NewLine
    )

    $terminal.SelectionColor = $green

    $terminal.SelectionStart = $terminal.TextLength

    $terminal.ScrollToCaret()
}

function Clear-Terminal {

    $terminal.Clear()

    Write-Terminal 'StockTerminal Launcher'
    Write-Terminal '------------------------------'
}

# ============================================================
# OUTPUT QUEUE
# ============================================================

# ConcurrentQueue allows background process output handlers
# to safely send messages to the Windows Forms UI thread.

$script:outputQueue = New-Object 'System.Collections.Concurrent.ConcurrentQueue[string]'

function Drain-OutputQueue {

    $line = ''

    while ($script:outputQueue.TryDequeue([ref]$line)) {

        if ($line.StartsWith('ERR:')) {

            Write-Terminal $line.Substring(4) $red

        } else {

            Write-Terminal $line $green
        }

        $line = ''
    }
}

# ============================================================
# PROCESS OUTPUT EVENTS
# ============================================================

# Use PowerShell event actions to read process output without
# blocking the Windows Forms message loop.

function Register-ProcessOutput($process) {

    $queue = $script:outputQueue

    $stdoutAction = {

        $line = $EventArgs.Data

        if ($null -ne $line) {

            $queue.Enqueue($line)
        }
    }

    $stderrAction = {

        $line = $EventArgs.Data

        if ($null -ne $line) {

            $queue.Enqueue('ERR:' + $line)
        }
    }

    Register-ObjectEvent `
        -InputObject $process `
        -EventName OutputDataReceived `
        -SourceIdentifier 'StockTerminal.Stdout' `
        -MessageData $queue `
        -Action {

            if ($null -ne $EventArgs.Data) {

                $Event.MessageData.Enqueue(
                    $EventArgs.Data
                )
            }

        } | Out-Null

    Register-ObjectEvent `
        -InputObject $process `
        -EventName ErrorDataReceived `
        -SourceIdentifier 'StockTerminal.Stderr' `
        -MessageData $queue `
        -Action {

            if ($null -ne $EventArgs.Data) {

                $Event.MessageData.Enqueue(
                    'ERR:' + $EventArgs.Data
                )
            }

        } | Out-Null

    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
}

function Unregister-ProcessOutput {

    Unregister-Event `
        -SourceIdentifier 'StockTerminal.Stdout' `
        -ErrorAction SilentlyContinue

    Unregister-Event `
        -SourceIdentifier 'StockTerminal.Stderr' `
        -ErrorAction SilentlyContinue

    Get-Job -Name 'StockTerminal.*' -ErrorAction SilentlyContinue |
        Remove-Job -Force -ErrorAction SilentlyContinue
}

# ============================================================
# PID FILE
# ============================================================

function Clear-PidFile {

    if ($script:pidFile) {

        try {

            $cleanup = New-WSLProcess (
                'rm -f ' + $script:pidFile
            )

            if ($cleanup) {
                $cleanup.Dispose()
            }

        } catch { }

        $script:pidFile = $null
    }
}

# ============================================================
# APPLICATION STATE
# ============================================================

function Set-State($name, $detail, $color, $activityText) {

    $stateLabel.Text = $name

    $stateLabel.ForeColor = $color

    $dot.BackColor = $color

    $detailLabel.Text = $detail

    $activity.Text = $activityText
}

function Set-Ready {

    Set-State `
        'READY' `
        'Ready to start StockTerminal.' `
        $green `
        'STANDBY // LOCAL RESEARCH ENVIRONMENT'

    $launch.Text = 'LAUNCH >'

    $launch.BackColor = [System.Drawing.Color]::FromArgb(40, 145, 88)

    $launch.Enabled = $true

    $script:stopping = $false
}

function Set-Running {

    Set-State `
        'RUNNING' `
        'StockTerminal is active in WSL.' `
        $green `
        'ACTIVE // STOCKTERMINAL IS RUNNING'

    $launch.Text = 'STOP X'

    $launch.BackColor = $red

    $launch.Enabled = $true

    $script:stopping = $false
}

function Set-Crashed($exitCode) {

    Set-State `
        'EXITED' `
        "StockTerminal exited with code $exitCode." `
        $red `
        'APPLICATION EXITED // REVIEW TERMINAL OUTPUT'

    $launch.Text = 'RELAUNCH >'

    $launch.BackColor = [System.Drawing.Color]::FromArgb(40, 145, 88)

    $launch.Enabled = $true

    $script:stopping = $false

    $terminalStatus.Text = "Process exited with code $exitCode"

    Write-Terminal (
        "StockTerminal exited with code $exitCode"
    ) $red
}

# ============================================================
# PROCESS CLEANUP
# ============================================================

function Finish-Process {

    if (-not $script:process) {
        return
    }

    $exitCode = $script:process.ExitCode

    try {
        $script:process.Dispose()
    } catch { }

    $script:process = $null

    Unregister-ProcessOutput

    Clear-PidFile

    if ($script:requestedStop) {

        Write-Terminal 'StockTerminal stopped.' $amber

        $script:requestedStop = $false

        Set-Ready

    } else {

        Set-Crashed $exitCode
    }
}

# ============================================================
# LAUNCH / STOP
# ============================================================

$launch.Add_Click({

    # --------------------------------------------------------
    # STOP APPLICATION
    # --------------------------------------------------------

    if (
        $script:process -and
        -not $script:process.HasExited
    ) {

        if ($script:stopping) {
            return
        }

        $script:stopping = $true
        $script:requestedStop = $true

        Set-State `
            'STOPPING' `
            'Sending shutdown request...' `
            $amber `
            'PLEASE WAIT // STOPPING APPLICATION'

        $launch.Enabled = $false

        Write-Terminal 'Sending SIGTERM to StockTerminal...' $amber

        try {

            $stopCommand = (
                'for i in 1 2 3 4 5; do ' +
                'if [ -s ' + $script:pidFile + ' ]; then ' +
                'kill -TERM $(cat ' + $script:pidFile + '); exit $?; ' +
                'fi; sleep 1; done; exit 1'
            )

            $script:stopProcess = New-WSLProcess $stopCommand

            if (-not $script:stopProcess) {
                throw 'Failed to start stop request.'
            }

            $script:stopDeadline = [datetime]::Now.AddSeconds(8)

        } catch {

            Write-Terminal $_.Exception.Message $red

            $script:requestedStop = $false

            Set-Running
        }

        return
    }

    # --------------------------------------------------------
    # START APPLICATION
    # --------------------------------------------------------

    $launch.Enabled = $false

    Clear-Terminal

    Set-State `
        'STARTING' `
        'Launching StockTerminal through WSL...' `
        $amber `
        'PLEASE WAIT // STARTING APPLICATION'

    $terminalStatus.Text = 'Starting WSL Ubuntu...'

    Write-Terminal 'Starting StockTerminal...' $amber

    Write-Terminal "Project: $project"

    Write-Terminal "Python: $python"

    Write-Terminal ''

    try {

        $script:requestedStop = $false

        $script:pidFile = (
            '/tmp/stockterminal-launcher-' +
            [guid]::NewGuid().ToString('N') +
            '.pid'
        )

        # PYTHONUNBUFFERED ensures print() messages are immediate.
        # exec replaces bash with Python while retaining the PID.

        $command = (
            'cd ' + $project +
            ' && echo $$ > ' + $script:pidFile +
            ' && exec env PYTHONUNBUFFERED=1 ' +
            $python +
            ' -u main.py'
        )

        $script:process = New-WSLProcess $command $true

        Register-ProcessOutput $script:process

        $terminalStatus.Text = 'Connected to WSL process output.'

        Write-Terminal 'WSL process started.' $green

        Set-Running

    } catch {

        Write-Terminal (
            'LAUNCH ERROR: ' + $_.Exception.Message
        ) $red

        Unregister-ProcessOutput

        if ($script:process) {

            try {
                $script:process.Dispose()
            } catch { }

            $script:process = $null
        }

        Clear-PidFile

        Set-Crashed -1
    }
})

# ============================================================
# UI TIMER
# ============================================================

$timer = New-Object System.Windows.Forms.Timer

$timer.Interval = 200

$timer.Add_Tick({

    # Update terminal
    Drain-OutputQueue

    # Monitor stop request
    if ($script:stopProcess) {

        if ($script:stopProcess.HasExited) {

            $exitCode = $script:stopProcess.ExitCode

            $script:stopProcess.Dispose()

            $script:stopProcess = $null

            if (
                $exitCode -ne 0 -and
                $script:process -and
                -not $script:process.HasExited
            ) {

                Write-Terminal 'Failed to send shutdown signal.' $red

                $script:requestedStop = $false

                Set-Running
            }

        } elseif (
            [datetime]::Now -gt $script:stopDeadline
        ) {

            try {
                $script:stopProcess.Kill()
            } catch { }

            $script:stopProcess.Dispose()

            $script:stopProcess = $null

            Write-Terminal 'Stop request timed out.' $red

            $script:requestedStop = $false

            Set-Running
        }
    }

    # Monitor application
    if (
        $script:process -and
        $script:process.HasExited
    ) {

        Drain-OutputQueue

        Finish-Process
    }
})

$timer.Start()

# ============================================================
# WINDOW CLOSED
# ============================================================

$form.Add_FormClosed({

    $timer.Stop()

    $timer.Dispose()

    Unregister-ProcessOutput

    if ($script:stopProcess) {

        try {
            $script:stopProcess.Dispose()
        } catch { }
    }

    if ($script:process) {

        try {
            $script:process.Dispose()
        } catch { }
    }

    # Closing the launcher does not terminate StockTerminal.
})

# ============================================================
# START
# ============================================================

Clear-Terminal

[void]$form.ShowDialog()
