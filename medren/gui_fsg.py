import argparse
import csv
import datetime
import json
import logging
import os
import platform
import subprocess
import webbrowser
from copy import copy
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

import FreeSimpleGUI as sg  # noqa: N813
import pyperclip

from medren import __version__
from medren.backends import available_backends
from medren.consts import (
    DEFAULT_DATETIME_FORMAT,
    DEFAULT_PROFILE_NAME,
    DEFAULT_SEPARATOR,
    DEFAULT_TEMPLATE, file_types,
)
from medren.profiles import Modes, profile_keys, profiles
from medren.renamer import (
    MEDREN_DIR,
    PROFILES_DIR,
    Renamer,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

saved_keys = [
    'inputs', 'profile', 'pattern', 'backends',
]


# Settings file path
def load_settings(filename, is_profile=False) -> dict:
    try:
        if os.path.exists(filename):
            with open(filename) as f:
                values = json.load(f)
                filter_list = profile_keys if is_profile else saved_keys
                values = {key: values[key] for key in filter_list}
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


def load_profile(profile_name: str) -> dict:
    profile_name = (profile_name or DEFAULT_PROFILE_NAME)
    profile_filename = get_profile_filename(profile_name)
    if profile_filename.is_file():
        return load_settings(profile_filename, is_profile=True)
    else:
        profile = profiles.get(profile_name)
        if profile:
            return profile.get_vars()
    return {}


def save_profile(values, profile_name: str) -> None:
    profile_filename = get_profile_filename(profile_name)
    save_settings(values=values, filename=profile_filename, is_profile=True)


def delete_profile(profile_name: str):
    profile_filename = get_profile_filename(profile_name)
    if profile_filename.is_file():
        os.remove(profile_filename)


def get_profile_filename(profile_name: str):
    profile_name = (profile_name or DEFAULT_PROFILE_NAME) + '.json'
    profile_filename = PROFILES_DIR / profile_name
    return profile_filename


def parse_args():
    parser = argparse.ArgumentParser(description='Media Renaming GUI')
    parser.add_argument(dest='inputs', nargs='*', help='Input paths (dirs, filenames or pattern)')
    parser.add_argument('--profile', '-P', help='Profile name')
    parser.add_argument('--template', '-t', help='Initial template value')
    parser.add_argument('--datetime-format', '-d', help='Initial datetime format value')
    parser.add_argument('--prefix', '-p', help='Initial prefix value')
    parser.add_argument('--suffix', '-s', help='Initial suffix value')
    return parser.parse_args()


def update_profile_list():
    pass


def get_profile_names():
    saved_profile_names = [p.stem for p in PROFILES_DIR.glob('*.json')]
    built_in_profile_names = list(profiles.keys())
    all_profile_names = sorted(set(saved_profile_names) | set(built_in_profile_names))
    return saved_profile_names, built_in_profile_names, all_profile_names


def override_settings(d: dict[str, Any], overrides: dict[str, Any]):
    for k, v in overrides.items():
        if v:
            d[k] = v
    return d


def main():  # noqa: PLR0915, PLR0912
    args = parse_args()

    # Load saved values or use command line arguments
    settings_filename = MEDREN_DIR / 'medren_settings.json'
    loaded_values = load_settings(settings_filename)

    saved_profile_names, built_in_profile_names, all_profile_names = get_profile_names()

    args_vars = vars(args)
    if args.profile:
        loaded_values['profile'] = args.profile

    profile_name = loaded_values.get('profile')
    loaded_values = override_settings(loaded_values, load_profile(profile_name))
    loaded_values = override_settings(loaded_values, args_vars)

    separators_layout = [sg.Text('separator:'),
                         sg.Input(default_text=DEFAULT_SEPARATOR, key='separator', tooltip='{s}', size=(3, 1))]

    # Top-left layout (multi-line form section)
    top_left_layout = [
        [sg.Text('Path:'),
         sg.Input(key='-PATH-', enable_events=True, expand_x=True),
         sg.FileBrowse(button_text='Browse', key='-BROWSE-', file_types=(('All Files', '*.*'),)),
         sg.Combo(list(file_types.keys()), default_value="*", key='pattern', readonly=False, size=(10, 1)),
         sg.Text('Mode:'), sg.Combo([m.name for m in Modes], default_value=Modes.dir.name, key='mode', readonly=True),
         ],

        [sg.Text('Profile:'),
         sg.Combo(all_profile_names, default_value=DEFAULT_PROFILE_NAME, key='profile', size=(15, 1)),
         sg.Button('Load Profile'),
         sg.Button('Save Profile'),
         sg.Button('Delete Profile'),
         ],

        [
            sg.Button('Add'),
            sg.Button('Preview'),
            sg.Button('Rename'),
            sg.Button('Clear'),
            sg.Button('Load Settings'),
            sg.Button('Save Settings'),
        ],

        [sg.Text('Template:'), sg.Input(default_text=DEFAULT_TEMPLATE, expand_x=True, key='template', size=(30, 1))],

        [sg.Text('Datetime Format:'),
         sg.Input(default_text=DEFAULT_DATETIME_FORMAT, expand_x=True, key='datetime_format', size=(20, 1))],

        [sg.Text('Prefix:'), sg.Input(expand_x=True, key='prefix', size=(15, 1)),
         sg.Text('Suffix:'), sg.Input(expand_x=True, key='suffix', size=(15, 1))],

        [*separators_layout,
         sg.Checkbox('Normalize', default=True, key='normalize', expand_x=True),
         sg.Checkbox('show full paths in table', default=True, key='org_full_path', expand_x=True),
         sg.Text('Items found:'), sg.Text('', key='-ITEMS-FOUND-', size=(10, 1)),
         ]
    ]

    # Wrap top-left layout in a Column
    top_left_column = sg.Column(top_left_layout, vertical_alignment='top', expand_x=True)

    # Top-right with listbox
    class InputsRightClickCommand(Enum):
        clear_inputs = 'Clear Inputs'

    inputs_right_click_items = [c.value for c in InputsRightClickCommand]
    top_right_column = sg.Column([
        [sg.Text('Added Input Paths:'), sg.Button('About MedRen v' + __version__, key='-VERSION-')],
        [sg.Listbox(values=[], size=(50, 8), key='inputs', expand_x=True, expand_y=True)]
    ], vertical_alignment='top', right_click_menu=['', inputs_right_click_items])

    class BackendsRightClickCommand(Enum):
        backend_move_to_top = 'Move backend to the top'
        backend_move_to_bottom = 'Move backend to the bottom'
        backend_remove = 'Remove backend'
        backend_reset = 'Reset backends priorities'

    backends_right_click_items = [c.value for c in BackendsRightClickCommand]
    top_right_column2 = sg.Column([
        [sg.Text('Backends:')],
        [sg.Listbox(values=available_backends, size=(10, 8), key='backends', expand_x=True, expand_y=True)]
    ], vertical_alignment='top', right_click_menu=['', backends_right_click_items])

    # Bottom layout: table
    class TableRightClickCommand(Enum):
        open_file = "Open selected File(s)"
        open_map = "Open OpenStreetMap of the selected files' geo locations"
        copy_org_filename = 'Copy Original'
        copy_new_filename = 'Copy New'
        copy_org_and_new_filenames = 'Copy Original -> New'
        copy_csv = 'Copy CSV'
        save_exif_csv = 'Save Exif data to csv file'
        select_all = 'Select all items'
        inverse_selection = 'Inverse selection'

    table_right_click_items = [c.value for c in TableRightClickCommand]
    bottom_layout = [sg.Table(
        values=[],
        headings=['Original Filename', 'New Filename', 'Datetime', 't_offset', 'make', 'model', 'Backend'],
        auto_size_columns=False,
        col_widths=[40, 30, 8, 2, 5, 8, 5],
        justification='left',
        key='-TABLE-',
        expand_x=True,
        expand_y=True,
        right_click_menu=['', table_right_click_items],
        bind_return_key=True,
    )]

    # Final layout
    layout = [
        [top_left_column, top_right_column2, top_right_column],
        [bottom_layout]
    ]

    window = sg.Window('MedRen - The Media Renamer', layout,
                       size=loaded_values.get('window_size', (900, 500)),
                       location=loaded_values.get('window_position'),
                       resizable=True, finalize=True)
    window['-TABLE-'].bind('<Double-Button-1>', '::DoubleClick')

    window.read(timeout=0)
    for key in loaded_values:
        window[key].update(loaded_values[key])
    # window['inputs'].Widget.select_set(0)

    renamer = None
    data = {}
    table_data = []

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        profile_name = values.get('profile', DEFAULT_PROFILE_NAME)
        # input_paths = values['inputs']
        input_paths = window['inputs'].Values
        selected = values['-TABLE-']

        if event == '-VERSION-':
            sg.popup(f'MedRen - The Media Renamer v{__version__}. By Idan Miara',
                     title='לאבא באהבה 😍')
        elif event == 'Save Settings':
            try:
                if sg.popup_yes_no('Would you like to save settings?', title='Save Settings'):
                    values = copy(values)
                    values["backends"] = list(window['backends'].Values)
                    save_settings(values=values, filename=settings_filename)
            except Exception as e:
                logger.error(f"Error saving settings: {e}")

        elif event == 'Load Settings':
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
                    saved_profile_names, built_in_profile_names, all_profile_names = get_profile_names()
                    window['profile'].update(value=profile_name, values=all_profile_names)

            except Exception as e:
                logger.error(f"Error saving profile {profile_name}: {e}")

        elif event == 'Load Profile':
            try:
                if sg.popup_yes_no(f'Would you like to load profile {profile_name}?', title='Load Profile'):
                    values = load_profile(profile_name)
                    for key in values:
                        window[key].update(values[key])

            except Exception as e:
                logger.error(f"Error loading profile {profile_name}: {e}")

        elif event == 'Delete Profile':
            try:
                is_builtin_profile = profile_name in built_in_profile_names
                msg = f'restore profile {profile_name} to default' if is_builtin_profile \
                    else f'delete profile {profile_name}'
                if sg.popup_yes_no(f'Would you like to {msg}?', title='Load Profile'):
                    delete_profile(profile_name)
                    if is_builtin_profile:
                        load_profile(profile_name)

            except Exception as e:
                logger.error(f"Error loading profile {profile_name}: {e}")

        # Handle file/directory selection
        elif event == '-PATH-':
            pass

        elif event == 'Add':
            path = values['-PATH-'].strip()
            if not path:
                continue
            path = Path(path)
            if not path:
                continue
            paths = []
            if values['mode'] == Modes.file.name:
                paths.append(path)
            else:
                patterns = values["pattern"]
                patterns = file_types.get(patterns, [patterns])
                if not path.is_dir():
                    path = path.parent
                if values['mode'] == Modes.recursive.name:
                    path = path / '**'
                # elif values['mode'] == Modes.dir.name:
                #     pass
                for pattern in patterns:
                    paths.append(path / pattern)
            for path in paths:
                if path not in input_paths:
                    input_paths.append(path)
                    window['inputs'].update(input_paths)
                    # window['inputs'].Widget.select_set(0)

        elif event == 'Clear':
            # input_paths.clear()
            table_data = []
            window['inputs'].update([])
            # window['inputs'].Widget.select_set(0)
            window['-TABLE-'].update(table_data)
            data = {}
            renamer = None

        elif event == 'Preview':
            if not input_paths:
                continue
            recursive = values['mode'] == 'recursive'
            renamer = Renamer(
                prefix=values['prefix'],
                template=values['template'],
                datetime_format=values['datetime_format'],
                separator=values['separator'],
                normalize=values['normalize'],
                suffix=values['suffix'],
                backends=list(window['backends'].Values),
                recursive=recursive,
            )
            data = renamer.generate_renames(input_paths, resolve_names=True)
            table_data = [[orig_fn, new_fn, ex.dt, ex.t_offset, ex.make, ex.model, ex.backend]
                          for orig_fn, (new_fn, ex) in data.items()]
            if not values['org_full_path']:
                for item in table_data:
                    item[0] = Path(item[0]).name
            window['-TABLE-'].update(values=table_data)
            window['-ITEMS-FOUND-'].update(len(table_data))

        elif event == 'Rename':
            if data and renamer:
                log_filename = datetime.datetime.now().strftime(values['datetime_format']) + '.log'
                renamer.apply_rename(data, logfile=MEDREN_DIR / 'logs' / log_filename)
                sg.popup('Renaming complete!')
                window['-TABLE-'].update([])
            else:
                sg.popup('Nothing to rename. Please preview first.')

        elif event == InputsRightClickCommand.clear_inputs.value:
            window['inputs'].update([])

        elif event == TableRightClickCommand.select_all.value:
            all_indices = list(range(len(data)))
            window['-TABLE-'].update(select_rows=all_indices)

        elif event == TableRightClickCommand.inverse_selection.value:
            all_indices = set(range(len(data)))
            new_selection = sorted(all_indices - set(selected))
            window['-TABLE-'].update(select_rows=new_selection)

        elif event == TableRightClickCommand.save_exif_csv.value:
            if not selected:
                continue
            # Open a "Save As" dialog for CSV file
            output_filename = sg.popup_get_file(
                'Save CSV As',
                save_as=True,
                file_types=(("CSV Files", "*.csv"),),
                default_extension=".csv",
                no_window=True
            )

            _, exif0 = next(iter(data.values()))
            fields = ["filename"] + list(asdict(exif0).keys())
           # Write to CSV
            selected_data = {k: v for idx, (k, v) in enumerate(data.items()) if idx in selected}
            with open(output_filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                for filename, (_, ex) in selected_data.items():
                    d = asdict(ex)
                    d['filename'] = filename
                    writer.writerow(d)

        elif event == '-TABLE-::DoubleClick':
            if not selected:
                continue
            all_filenames = list(data.keys())
            filename = all_filenames[selected[0]]
            open_with_default_app(filename)

        elif event == TableRightClickCommand.open_file.value:
            if not selected:
                continue
            all_filenames = list(data.keys())
            selected_filenames = [all_filenames[i] for i in selected]
            count = len(selected_filenames)
            if count <= 5 or sg.popup_yes_no(f'Would you like to open the {count} selected files?', title=f'Open {count} files'):
                for filename in selected_filenames:
                    open_with_default_app(filename)

        elif event == TableRightClickCommand.open_map.value:
            if not selected:
                continue
            selected_data = {k: v for idx, (k, v) in enumerate(data.items()) if idx in selected}
            count = len(selected_data)
            zoom = 18
            found = 0
            if count <= 5 or sg.popup_yes_no(f'Would you like to open the {count} selected files?', title=f'Open {count} files'):
                for filename, (_, ex) in selected_data.items():
                    lat, lon = ex.lat, ex.lon
                    if lat is None or lon is None:
                        continue
                    found += 1
                    # url = f"https://www.openstreetmap.org/#map=18/{lat}/{lon}"
                    url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom={zoom}"
                    webbrowser.open(url)
                if not found:
                    sg.popup('Selected files have geo location info')

        elif event in table_right_click_items:
            if not selected:
                continue
            elif event == TableRightClickCommand.copy_org_filename.value:
                text = '\n'.join(f"{table_data[i][0]}" for i in selected)
            elif event == TableRightClickCommand.copy_new_filename.value:
                text = '\n'.join(f"{table_data[i][1]}" for i in selected)
            elif event == TableRightClickCommand.copy_org_and_new_filenames.value:
                text = '\n'.join(f"{table_data[i][0]} -> {table_data[i][1]}" for i in selected)
            elif event == TableRightClickCommand.copy_csv.value:
                text = '\n'.join(f"{','.join([str(x) for x in table_data[i]])}" for i in selected)
            else:
                text = 'Unknown operation'
            pyperclip.copy(text)

        elif event in backends_right_click_items:
            if event == BackendsRightClickCommand.backend_reset.value:
                backends = list(available_backends)
            else:
                move_to_top = event == BackendsRightClickCommand.backend_move_to_top.value
                remove_backend = event == BackendsRightClickCommand.backend_remove.value
                selected = values['backends']
                backends = list(window['backends'].Values)
                for item in selected:
                    backends.remove(item)
                    if remove_backend:
                        pass
                    elif move_to_top:
                        backends.insert(0, item)
                    else:
                        backends.append(item)
            window['backends'].update(values=backends)

    window.close()


def open_with_default_app(filepath):
    if platform.system() == 'Windows':
        os.startfile(filepath)
    elif platform.system() == 'Darwin':  # macOS
        subprocess.run(['open', filepath])
    else:  # Linux and others
        subprocess.run(['xdg-open', filepath])


if __name__ == '__main__':
    main()
