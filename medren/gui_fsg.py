import datetime
import os
import sys
import argparse
import logging
from pathlib import Path
import FreeSimpleGUI as sg
import json
import pyperclip

from medren import __version__
from medren.renamer import Renamer, DEFAULT_DATETIME_FORMAT, DEFAULT_TEMPLATE, DEFAULT_SEPERATOR, MEDREN_DIR, DEFAULT_PROFILE_NAME, PROFILES_DIR

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

saved_keys = [
    '-INPUTS-', '-PROFILE-',
    ]

profile_keys = [
    '-PREFIX-', '-TEMPLATE-', '-DATETIME-FORMAT-', '-SUFFIX-', '-MODE-', '-NORMALIZE-', '-ORG-FULL-PATH-', 
    '-SEPERATOR-PREFIX-', '-SEPERATOR-INDEX-', '-SEPERATOR-NAME-', '-SEPERATOR-DATETIME-'
]

# Settings file path
def load_settings(filename, is_profile=False) -> dict:
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                values = json.load(f)
                filter = profile_keys if is_profile else saved_keys
                values = {key: values[key] for key in filter}
                return values
    except Exception:
        pass
    return {}

def save_settings(values, filename, is_profile=False) -> None:
    filter = profile_keys if is_profile else saved_keys
    values = {key: values[key] for key in filter}
    try:
        with open(filename, 'w') as f:
            json.dump(values, f)
    except Exception:
        pass

def load_profile(profile_name) -> dict:
    profile_name = (profile_name or DEFAULT_PROFILE_NAME) + '.json'
    profile_filename = PROFILES_DIR / profile_name    
    return load_settings(profile_filename, is_profile=True)


def save_profile(values, profile_name) -> None:
    profile_name = (profile_name or DEFAULT_PROFILE_NAME) + '.json'
    profile_filename = PROFILES_DIR / profile_name    
    save_settings(values=values, filename=profile_filename, is_profile=True)


def parse_args():
    parser = argparse.ArgumentParser(description='Media Renaming GUI')
    parser.add_argument(dest='inputs', nargs='*', help='Input paths (dirs, filenames or pattern)')
    parser.add_argument('--prefix', '-p', help='Initial prefix value')
    parser.add_argument('--suffix', '-s', help='Initial suffix value')
    parser.add_argument('--profile', '-P', help='Profile name')
    parser.add_argument('--template', '-t', help='Initial template value')
    parser.add_argument('--datetime-format', '-f', help='Initial datetime format value')
    parser.add_argument('--separator-prefix', '--sp', help='Separator between prefix and index')
    parser.add_argument('--separator-index', '--si', help='Separator between index and datetime')
    parser.add_argument('--separator-datetime', '--sd', help='Separator between datetime and name')
    parser.add_argument('--separator-name', '--sn', help='Separator between name and suffix')
    parser.add_argument('--no-normalize', action='store_true', help='Disable filename normalization')
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Load saved values or use command line arguments
    settings_filename = MEDREN_DIR / 'medren_settings.json'
    values = load_settings(settings_filename)    
    profile_names = [p.stem for p in PROFILES_DIR.glob('*.json')]
    
    if args.profile:
        values['-PROFILE-'] = args.profile
    
    profile_name = values.get('-PROFILE-')
    values = values | load_profile(profile_name)
    
    if args.inputs: 
        values['-INPUTS-'] = list(args.inputs)
    if args.prefix:
        values['-PREFIX-'] = args.prefix
    if args.template:
        values['-TEMPLATE-'] = args.template
    if args.datetime_format:
        values['-DATETIME-FORMAT-'] = args.datetime_format
    if args.suffix:
        values['-SUFFIX-'] = args.suffix
    if args.separator_prefix:
        values['-SEPERATOR-PREFIX-'] = args.separator_prefix
    if args.separator_index:
        values['-SEPERATOR-INDEX-'] = args.separator_index
    if args.separator_name:
        values['-SEPERATOR-NAME-'] = args.separator_name
    if args.separator_datetime:
        values['-SEPERATOR-DATETIME-'] = args.separator_datetime
    if args.no_normalize:
        values['-NORMALIZE-'] = False


    # Top-left layout (multi-line form section)
    top_left_layout = [
        [sg.Text('Path:'), 
        sg.Input(values.get('-PATH-'), key='-PATH-', enable_events=True, expand_x=True), 
        sg.FileBrowse(button_text='Browse', key='-BROWSE-', file_types=(('All Files', '*.*'),))],
        
        [sg.Text('Profile:'), 
         sg.Combo(profile_names, default_value=values.get('-PROFILE-', DEFAULT_PROFILE_NAME), key='-PROFILE-', size=(15, 1)), 
         sg.Button('Save Profile'), 
         sg.Button('Load Profile')],
        
        [
        sg.Button('Add'), 
        sg.Button('Preview'), 
        sg.Button('Rename'),
        sg.Button('Clear'),
        sg.Button('Save'),
        sg.Button('Load'),
        sg.Text('Mode:'), sg.Combo(['file', 'dir', 'recursive'], default_value=values.get('-MODE-', 'dir'), key='-MODE-', readonly=True)],
        
        [sg.Text('Template:'), sg.Input(default_text=values.get('-TEMPLATE-', DEFAULT_TEMPLATE), expand_x=True, key='-TEMPLATE-', size=(30, 1))],

        [sg.Text('Datetime Format:'), sg.Input(default_text=values.get('-DATETIME-FORMAT-', DEFAULT_DATETIME_FORMAT), expand_x=True, key='-DATETIME-FORMAT-', size=(20, 1))],

        [sg.Text('Prefix:'), sg.Input(expand_x=True, key='-PREFIX-', size=(15, 1)),
        sg.Text('Suffix:'), sg.Input(expand_x=True, key='-SUFFIX-', size=(15, 1))],
        
        [sg.Text('sp:'), sg.Input(default_text=DEFAULT_SEPERATOR, key='-SEPERATOR-PREFIX-', size=(3, 1)),
        sg.Text('si:'), sg.Input(default_text=DEFAULT_SEPERATOR, key='-SEPERATOR-INDEX-', size=(3, 1)),
        sg.Text('sn:'), sg.Input(default_text=DEFAULT_SEPERATOR, key='-SEPERATOR-NAME-', size=(3, 1)),
        sg.Text('sd:'), sg.Input(default_text=DEFAULT_SEPERATOR, key='-SEPERATOR-DATETIME-', size=(3, 1)),
        sg.Checkbox('Normalize', default=True, key='-NORMALIZE-', expand_x=True),
        sg.Checkbox('show full paths in table', default= True, key='-ORG-FULL-PATH-', expand_x=True),
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
    right_click_menu = ['', ['Copy Original', 'Copy New', 'Copy Both']]

    # Bottom layout: table
    bottom_layout = [sg.Table(
        values=[],
        headings=['Original Filename', 'New Filename'],
        auto_size_columns=False,
        col_widths=[60, 40],
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
                    size=values.get('window_size', (900, 500)), 
                    location=values.get('window_position'),
                    resizable=True)
    renamer, preview = None, {}
    table_data = []
    preview = []

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED:
            break
        profile_name = values.get('-PROFILE-', DEFAULT_PROFILE_NAME)
        input_paths = values['-INPUTS-']
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
                window['-INPUTS-'].Widget.select_set(0)
                
        elif event == 'Clear':
            input_paths.clear()
            table_data = []
            window['-INPUTS-'].update(input_paths)
            window['-INPUTS-'].Widget.select_set(0)
            window['-TABLE-'].update(table_data)
            preview = {}
            renamer = None
            
        elif event == 'Preview':
            if input_paths:
                renamer = Renamer(
                    prefix=values['-PREFIX-'],
                    template=values['-TEMPLATE-'],
                    datetime_format=values['-DATETIME-FORMAT-'],
                    sp=values['-SEPERATOR-PREFIX-'],
                    si=values['-SEPERATOR-INDEX-'],
                    sd=values['-SEPERATOR-DATETIME-'],
                    sn=values['-SEPERATOR-NAME-'],
                    normalize=values['-NORMALIZE-'],
                    suffix=values['-SUFFIX-'],
                )
                resolved_inputs = renamer.resolve_names(input_paths)
                preview = renamer.generate_renames(resolved_inputs, resolve_names=True)
                if values['-ORG-FULL-PATH-']:
                    table_data = list(preview.items())
                else:
                    table_data = [[Path(orig).name, new] for orig, new in preview.items()]
                window['-TABLE-'].update(values=table_data)
                
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
                if event == 'Copy Original':
                    text = '\n'.join(table_data[i][0] for i in values['-TABLE-'])
                elif event == 'Copy New':
                    text = '\n'.join(table_data[i][1] for i in values['-TABLE-'])
                elif event == 'Copy Both':
                    text = '\n'.join(f"{table_data[i][0]} -> {table_data[i][1]}" for i in values['-TABLE-'])
                pyperclip.copy(text)

    window.close()

if __name__ == '__main__':
    main()
