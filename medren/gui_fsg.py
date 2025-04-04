import argparse
import datetime
import json
import logging
import os
from enum import Enum
from pathlib import Path

import FreeSimpleGUI as sg  # noqa: N813
import pyperclip

from medren import __version__
from medren.renamer import (
    MEDREN_DIR,
    PROFILES_DIR,
    Renamer,
)
from medren.consts import (
    DEFAULT_DATETIME_FORMAT,
    DEFAULT_EXIF_FORMAT,
    DEFAULT_PROFILE_NAME,
    DEFAULT_SEPERATOR,
    DEFAULT_TEMPLATE,
)
from medren.profiles import Modes, key_to_gui_key, profile_keys, sep_abbr, profiles

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

saved_keys = [
    '-INPUTS-', '-PROFILE-',
    ]

# Settings file path
def load_settings(filename, is_profile=False) -> dict:
    try:
        if os.path.exists(filename):
            with open(filename) as f:
                values = json.load(f)
                filter = profile_keys if is_profile else saved_keys
                values = {key: values[key] for key in filter}
                return values
    except Exception:
        pass
    return {}

def save_settings(values, filename, is_profile=False) -> None:
    filter_list = profile_keys if is_profile else saved_keys
    values = {key: values[key] for key in filter_list}
    try:
        with open(filename, 'w') as f:
            json.dump(values, f)
    except Exception:
        pass

def load_profile(profile_name) -> dict:
    profile_name = (profile_name or DEFAULT_PROFILE_NAME)
    profile_filename = PROFILES_DIR / (profile_name + '.json')
    if profile_filename.is_file():
        return load_settings(profile_filename, is_profile=True)
    else:
        profile = profiles.get(profile_name)
        if profile:
            return vars(profile)
    return {}


def save_profile(values, profile_name) -> None:
    profile_name = (profile_name or DEFAULT_PROFILE_NAME) + '.json'
    profile_filename = PROFILES_DIR / profile_name
    save_settings(values=values, filename=profile_filename, is_profile=True)


def parse_args():
    parser = argparse.ArgumentParser(description='Media Renaming GUI')
    parser.add_argument(dest='inputs', nargs='*', help='Input paths (dirs, filenames or pattern)')
    parser.add_argument('--profile', '-P', help='Profile name')
    parser.add_argument('--template', '-t', help='Initial template value')
    parser.add_argument('--datetime-format', '-d', help='Initial datetime format value')
    parser.add_argument('--exif-format', '-e', help='Initial exif format value')
    parser.add_argument('--prefix', '-p', help='Initial prefix value')
    parser.add_argument('--suffix', '-s', help='Initial suffix value')
    return parser.parse_args()

def main():  # noqa: PLR0915, PLR0912
    args = parse_args()

    # Load saved values or use command line arguments
    settings_filename = MEDREN_DIR / 'medren_settings.json'
    loaded_values = load_settings(settings_filename)
    saved_profile_names = [p.stem for p in PROFILES_DIR.glob('*.json')]
    built_in_profile_names = list(profiles.keys())
    all_profile_names = sorted(set(saved_profile_names) | set(built_in_profile_names))

    if args.profile:
        loaded_values['-PROFILE-'] = args.profile

    profile_name = loaded_values.get('-PROFILE-')
    loaded_values = loaded_values | load_profile(profile_name)

    if args.inputs:
        loaded_values['-INPUTS-'] = list(args.inputs)
    if args.prefix:
        loaded_values['-PREFIX-'] = args.prefix
    if args.suffix:
        loaded_values['-SUFFIX-'] = args.suffix
    if args.template:
        loaded_values['-TEMPLATE-'] = args.template
    if args.datetime_format:
        loaded_values['-DATETIME-FORMAT-'] = args.datetime_format
    if args.exif_format:
        loaded_values['-EXIF-FORMAT-'] = args.exif_format

    seperators_layout = []
    for k, v in sep_abbr.items():
        seperators_layout.append(sg.Text(f'{k}:'))
        seperators_layout.append(sg.Input(default_text=DEFAULT_SEPERATOR, key=f'-{v.gui_key}-', size=(3, 1)))

    # Top-left layout (multi-line form section)
    top_left_layout = [
        [sg.Text('Path:'),
        sg.Input(key='-PATH-', enable_events=True, expand_x=True),
        sg.FileBrowse(button_text='Browse', key='-BROWSE-', file_types=(('All Files', '*.*'),))],

        [sg.Text('Profile:'),
         sg.Combo(all_profile_names, default_value=DEFAULT_PROFILE_NAME, key='-PROFILE-', size=(15, 1)),
         sg.Button('Save Profile'),
         sg.Button('Load Profile')],

        [
        sg.Button('Add'),
        sg.Button('Preview'),
        sg.Button('Rename'),
        sg.Button('Clear'),
        sg.Button('Save'),
        sg.Button('Load'),
        sg.Text('Mode:'), sg.Combo([str(m) for m in Modes], default_value='dir', key='-MODE-', readonly=True)],

        [sg.Text('Template:'), sg.Input(default_text=DEFAULT_TEMPLATE, expand_x=True, key='-TEMPLATE-', size=(30, 1))],

        [sg.Text('Datetime Format:'),
         sg.Input(default_text=DEFAULT_DATETIME_FORMAT, expand_x=True, key='-DATETIME-FORMAT-', size=(20, 1))],
        [sg.Text('Exif Format:'),
         sg.Input(default_text=DEFAULT_EXIF_FORMAT, expand_x=True, key='-EXIF-FORMAT-', size=(20, 1))],

        [sg.Text('Prefix:'), sg.Input(expand_x=True, key='-PREFIX-', size=(15, 1)),
        sg.Text('Suffix:'), sg.Input(expand_x=True, key='-SUFFIX-', size=(15, 1))],

        [*seperators_layout,
        sg.Checkbox('Normalize', default=True, key='-NORMALIZE-', expand_x=True),
        sg.Checkbox('show full paths in table', default= True, key='-ORG-FULL-PATH-', expand_x=True),
        sg.Text('Items found:'), sg.Text('', key='-ITEMS-FOUND-', size=(10, 1)),
        ]
    ]

    # Wrap top-left layout in a Column
    top_left_column = sg.Column(top_left_layout, vertical_alignment='top', expand_x=True)

    # Top-right with listbox
    top_right_column = sg.Column([
        [sg.Text('Added Input Paths:'), sg.Button('About MedRen v' + __version__, key='-VERSION-')],
        [sg.Listbox(values=[], size=(100, 8), key='-INPUTS-', expand_x=True, expand_y=True)]
    ], vertical_alignment='top')

    # Right-click menu
    class RightClickCommand(Enum):
        org = 'Copy Original'
        new = 'Copy New'
        both = 'Copy Original -> New'
        csv = 'Copy CSV'
    right_click_menu = ['', [c.name for c in RightClickCommand]]

    # Bottom layout: table
    bottom_layout = [sg.Table(
        values=[],
        headings=['Original Filename', 'New Filename', 'Datetime', 'goff', 'exif', 'Backend'],
        auto_size_columns=False,
        col_widths=[40, 30, 10, 3, 10, 10],
        justification='left',
        key='-TABLE-',
        expand_x=True,
        expand_y=True,
        right_click_menu=right_click_menu
    )]

    # Final layout
    layout = [
        [top_left_column, top_right_column],
        [bottom_layout]
    ]

    window = sg.Window('MedRen - The Media Renamer', layout,
                    size=loaded_values.get('window_size', (900, 500)),
                    location=loaded_values.get('window_position'),
                    resizable=True)

    window.read(timeout=0)
    for key in loaded_values:
        window[key].update(loaded_values[key])
    # window['-INPUTS-'].Widget.select_set(0)

    renamer, preview = None, {}
    table_data = []
    preview = []

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        profile_name = values.get('-PROFILE-', DEFAULT_PROFILE_NAME)
        # input_paths = values['-INPUTS-']
        input_paths = window['-INPUTS-'].Values
        if event == '-VERSION-':
            sg.popup(f'MedRen - The Media Renamer v{__version__}. By Idan Miara',
                     title='לאבא באהבה 😍')
        elif event == 'Save':
            try:
                if sg.popup_yes_no('Would you like to save settings?', title='Save Settings'):
                    save_settings(values=values, filename=settings_filename)
            except Exception as e   :
                logger.error(f"Error saving settings: {e}")

        elif event == 'Load':
            try:
                if sg.popup_yes_no('Would you like to load settings?', title='Load Settings'):
                    values = load_settings(settings_filename)
                    for key in values:
                        window[key].update(values[key])

            except Exception as e:
                logger.error(f"Error loading settings: {e}")

        elif event == 'Save Profile':
            try:
                if sg.popup_yes_no(f'Would you like to save profile {profile_name}?', title='Save Profile'):
                    save_profile(values=values, profile_name=profile_name)
            except Exception as e   :
                logger.error(f"Error saving profile {profile_name}: {e}")

        elif event == 'Load Profile':
            try:
                if sg.popup_yes_no(f'Would you like to load profile {profile_name}?', title='Load Profile'):
                    values = load_profile(profile_name)
                    for key in values:
                        window[key].update(values[key])

            except Exception as e:
                logger.error(f"Error loading profile {profile_name}: {e}")

        # Handle file/directory selection
        elif event == '-PATH-':
            path = values['-PATH-']
            if values['-MODE-'] == 'file':
                window['-PATH-'].update(Path(path))
            elif values['-MODE-'] == 'recursive':
                window['-PATH-'].update(Path(path).parent / '**/*')
            else: # elif values['-MODE-'] == 'dir':
                window['-PATH-'].update(Path(path).parent / '*')

        elif event == 'Add':
            path = values['-PATH-']
            if path and path not in input_paths:
                input_paths.append(path)
                window['-INPUTS-'].update(input_paths)
                # window['-INPUTS-'].Widget.select_set(0)

        elif event == 'Clear':
            # input_paths.clear()
            table_data = []
            window['-INPUTS-'].update(input_paths)
            # window['-INPUTS-'].Widget.select_set(0)
            window['-TABLE-'].update(table_data)
            preview = {}
            renamer = None

        elif event == 'Preview':
            if input_paths:
                recursive = values['-MODE-'] == 'recursive'
                seperator_values = {k: values[v.gui_key()] for k, v in sep_abbr.items()}
                renamer = Renamer(
                    prefix=values['-PREFIX-'],
                    template=values['-TEMPLATE-'],
                    datetime_format=values['-DATETIME-FORMAT-'],
                    exif_format=values['-EXIF-FORMAT-'],
                    seperators=seperator_values,
                    normalize=values['-NORMALIZE-'],
                    suffix=values['-SUFFIX-'],
                    recursive=recursive,
                )
                preview = renamer.generate_renames(input_paths, resolve_names=True)
                table_data = [[orig, path, ex.dt, ex.goff, ex.make, ex.model, ex.backend]
                              for orig, (path, ex) in preview.items()]
                if not values['-ORG-FULL-PATH-']:
                    for item in table_data:
                        item[0] = Path(item[0]).name
                window['-TABLE-'].update(values=table_data)
                window['-ITEMS-FOUND-'].update(len(table_data))

        elif event == 'Rename':
            if preview and renamer:
                log_filename = datetime.datetime.now().strftime(values['-DATETIME-FORMAT-']) + '.log'
                renamer.apply_rename(preview, logfile=MEDREN_DIR / 'logs' / log_filename)
                sg.popup('Renaming complete!')
                window['-TABLE-'].update([])
            else:
                sg.popup('Nothing to rename. Please preview first.')

        elif event.startswith('Copy'):
            if values['-TABLE-']:
                if event == RightClickCommand.org.name:
                    text = '\n'.join(table_data[i][0] for i in values['-TABLE-'])
                elif event == RightClickCommand.new.name:
                    text = '\n'.join(table_data[i][1] for i in values['-TABLE-'])
                elif event == RightClickCommand.both.name:
                    text = '\n'.join(f"{table_data[i][0]} -> {table_data[i][1]}" for i in values['-TABLE-'])
                elif event == RightClickCommand.csv.name:
                    text = '\n'.join(f"{','.join(table_data[i])}" for i in values['-TABLE-'])
                else:
                    text = 'Unknown operation'
                pyperclip.copy(text)

    window.close()

if __name__ == '__main__':
    main()
