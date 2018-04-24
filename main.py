import os
import logging
import gi
import getpass
import multiprocessing

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')

from locale import atof, setlocale, LC_NUMERIC
from gi.repository import Notify
from itertools import islice
from subprocess import Popen, PIPE, check_call, call, CalledProcessError
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction


logger = logging.getLogger(__name__)
ext_icon = 'images/icon.png'
exec_icon = 'images/executable.png'
dead_icon = 'images/dead.png'


class ProcessKillerExtension(Extension):

    def __init__(self):
        super(ProcessKillerExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        setlocale(LC_NUMERIC, '')  # set to OS default locale;

    def show_notification(self, title, text=None, icon=ext_icon):
        logger.debug('Show notification: %s' % text)
        icon_full_path = os.path.join(os.path.dirname(__file__), icon)
        Notify.init("KillerExtension")
        Notify.Notification.new(title, text, icon_full_path).show()


class KeywordQueryEventListener(EventListener):

    def on_event(self, event, extension):
        return RenderResultListAction(list(islice(self.generate_results(event), 10)))

    def generate_results(self, event):
        for (pid, cmd, args) in get_process_list():
            name = ('%s' % (cmd))
            description = ('PID: %s\t%s ' % (pid, args))
            on_enter = {'alt_enter': False, 'pid': pid, 'cmd': cmd}
            on_alt_enter = on_enter.copy()
            on_alt_enter['alt_enter'] = True
            if event.get_argument():
                if event.get_argument() in cmd:
                    yield ExtensionResultItem(icon=exec_icon,
                                                   name=name,
                                                   description=description,
                                                   on_enter=ExtensionCustomAction(on_enter),
                                                   on_alt_enter=ExtensionCustomAction(on_alt_enter, keep_app_open=True))
            else:
                yield ExtensionResultItem(icon=exec_icon,
                                               name=name,
                                               description=description,
                                               on_enter=ExtensionCustomAction(on_enter),
                                               on_alt_enter=ExtensionCustomAction(on_alt_enter, keep_app_open=True))


class ItemEnterEventListener(EventListener):

    def kill(self, extension, pid, signal):
        cmd = ['kill', '-s', signal, pid]
        logger.info(' '.join(cmd))

        try:
            check_call(cmd) == 0
            extension.show_notification("Done", "It's dead now", icon=dead_icon)
        except CalledProcessError as e:
            extension.show_notification("Error", "'kill' returned code %s" % e.returncode)
        except Exception as e:
            logger.error('%s: %s' % (type(e).__name__, e.message))
            extension.show_notification("Error", "Check the logs")
            raise

    def show_signal_options(self, data):
        result_items = []
        options = [('TERM', '15 TERM (default)'), ('KILL', '9 KILL'), ('HUP', '1 HUP')]
        for sig, name in options:
            on_enter = data.copy()
            on_enter['alt_enter'] = False
            on_enter['signal'] = sig
            result_items.append(ExtensionResultItem(icon=ext_icon,
                                                         name=name,
                                                         description=description,
                                                         highlightable=False,
                                                         on_enter=ExtensionCustomAction(on_enter)))
        return RenderResultListAction(result_items)

    def on_event(self, event, extension):
        data = event.get_data()
        if data['alt_enter']:
            return self.show_signal_options(data)
        else:
            self.kill(extension, data['pid'], data.get('signal', 'TERM'))


def get_process_list():
    pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]
    user = getpass.getuser()

    pool = multiprocessing.Pool(multiprocessing.cpu_count())
    results = pool.map(getProcessInformation, pids)
    pool.close()

    gen = (result for result in results if result[1] == user)
    for result in gen:
        yield (result[0], result[3], result[2])

def getProcessInformation(pid):
    cmd_output = Popen(('ps -p %s -o user:32 -o args -o comm' % pid), shell=True, stdout=PIPE).stdout.read()
    lines = cmd_output.split('\n')
    out = lines[1].split()
    uname = out[0]
    args = out[1]
    cmd = out[2]
    return [pid, uname, args, cmd]

if __name__ == '__main__':
    ProcessKillerExtension().run()
