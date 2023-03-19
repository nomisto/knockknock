import os
import datetime
import traceback
import functools
import socket
import subprocess
import platform
import base64
from platform import uname

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def desktop_sender(title: str = "knockknock"):

    def in_wsl() -> bool:
        return 'microsoft-standard' in uname().release

    def encode_powershell_command(text: str, title: str):

        if text.startswith("Your training has crashed"):
            icon = "Error"
        else:
            icon = "Info"

        ps_command = "\n".join([
            "Add-Type -AssemblyName System.Windows.Forms",
            "$global:balloon = New-Object System.Windows.Forms.NotifyIcon",
            "$path = (Get-Process -id $pid).Path",
            "$balloon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($path)",
            "$balloon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::" + icon,
            "$balloon.BalloonTipTitle = \"" + title + "\"",
            "$balloon.BalloonTipText = \"" + text + "\"",
            "$balloon.Visible = $true",
            "$balloon.ShowBalloonTip(5000)"
        ])
        return base64.b64encode(ps_command.encode("utf-16-le"))
    
    def show_notification(text: str, title: str):
        # Check the OS
        if platform.system() == "Darwin":     
            subprocess.run(["sh", "-c", "osascript -e 'display notification \"%s\" with title \"%s\"'" % (text, title)])
        
        elif platform.system() == "Linux":
            if in_wsl():
                subprocess.run(["powershell.exe", "-EncodedCommand", encode_powershell_command(text, title)])
            else:   
                subprocess.run(["notify-send", title, text])
        
        elif platform.system() == "Windows":
            try:
                from win10toast import ToastNotifier
            except ImportError as err:
                print('Error: to use Windows Desktop Notifications, you need to install `win10toast` first. Please run `pip install win10toast==0.9`.')

            toaster = ToastNotifier()
            toaster.show_toast(title,
                               text,
                               icon_path=None,
                               duration=5)

    def decorator_sender(func):
        @functools.wraps(func)
        def wrapper_sender(*args, **kwargs):

            start_time = datetime.datetime.now()
            host_name = socket.gethostname()
            func_name = func.__name__

            # Handling distributed training edge case.
            # In PyTorch, the launch of `torch.distributed.launch` sets up a RANK environment variable for each process.
            # This can be used to detect the master process.
            # See https://github.com/pytorch/pytorch/blob/master/torch/distributed/launch.py#L211
            # Except for errors, only the master process will send notifications.
            if 'RANK' in os.environ:
                master_process = (int(os.environ['RANK']) == 0)
                host_name += ' - RANK: %s' % os.environ['RANK']
            else:
                master_process = True

            if master_process:
                contents = ['Your training has started 🎬',
                            'Machine name: %s' % host_name,
                            'Main call: %s' % func_name,
                            'Starting date: %s' % start_time.strftime(DATE_FORMAT)]
                text = '\n'.join(contents)
                show_notification(text, title)

            try:
                value = func(*args, **kwargs)

                if master_process:
                    end_time = datetime.datetime.now()
                    elapsed_time = end_time - start_time
                    contents = ["Your training is complete 🎉",
                                'Machine name: %s' % host_name,
                                'Main call: %s' % func_name,
                                'Starting date: %s' % start_time.strftime(DATE_FORMAT),
                                'End date: %s' % end_time.strftime(DATE_FORMAT),
                                'Training duration: %s' % str(elapsed_time)]

                    try:
                        str_value = str(value)
                        contents.append('Main call returned value: %s'% str_value)
                    except:
                        contents.append('Main call returned value: %s'% "ERROR - Couldn't str the returned value.")

                    text = '\n'.join(contents)
                    show_notification(text, title)

                return value

            except Exception as ex:
                end_time = datetime.datetime.now()
                elapsed_time = end_time - start_time
                contents = ["Your training has crashed ☠️",
                            'Machine name: %s' % host_name,
                            'Main call: %s' % func_name,
                            'Starting date: %s' % start_time.strftime(DATE_FORMAT),
                            'Crash date: %s' % end_time.strftime(DATE_FORMAT),
                            'Crashed training duration: %s\n\n' % str(elapsed_time),
                            "Here's the error:",
                            '%s\n\n' % ex,
                            "Traceback:",
                            '%s' % traceback.format_exc()]
                text = '\n'.join(contents)
                show_notification(text, title)
                raise ex

        return wrapper_sender

    return decorator_sender
