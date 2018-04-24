import os
import logging
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')

from locale import atof, setlocale, LC_NUMERIC
from gi.repository import Notify
from itertools import islice
from subprocess import Popen, PIPE, check_call, CalledProcessError
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
        return RenderResultListAction(list(islice(self.generate_results(event), 15)))

    def generate_results(self, event):
        for (pid, cpu, mem, cmd, cmd_long) in get_process_list():
            name = ('%s %s' % (cmd, pid))
            description = ('cpu %% : %s mem %% : %s loc : %s ' % (cpu, mem, cmd_long))
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
    """
    Returns a list of tuples (PID, CPU, MEM, COMMAND, LONG_COMMAND)
    """
    env = os.environ.copy()
    env['COLUMNS'] = '200'
    process = Popen(['top', '-bn1', '-u', os.getenv('USER')], stdout=PIPE, env=env)
    process_lc = Popen(['top', '-bn1', '-cu', os.getenv('USER')], stdout=PIPE, env=env)
    out = process.communicate()[0]
    lc_output = process_lc.communicate()[0].split('\n')
    for idx, line in enumerate(out.split('\n')):
        col = line.split()
        try:
            int(col[0])
        except (ValueError, IndexError):
            # not a number
            continue

        pid = col[0]
        cpu = atof(col[8])
        mem = atof(col[9])
        cmd = ' '.join(col[11:])
        try:
            cmd_long = lc_output[idx].split()[11]
        except (ValueError, IndexError):
            cmd_long = ""
        if 'top -bn' in cmd:
            continue

        yield (pid, cpu, mem, cmd, cmd_long)


if __name__ == '__main__':
    ProcessKillerExtension().run()
