#!/usr/bin/env python3

import PySimpleGUI as sg
import math

GUI_TITLE = 'Screen Scaling Example'
GUI_TEXT_SIZE = (55,1)
GUI_REF_DPI = 72
MM_PER_INCH = 25.4

# sg.set_options(font='Courier 10')

class Parameters:
    screen_scaling = None
    screen_host = None
    screen_width_px = None
    screen_height_px = None
    display_width_mm = None
    display_height_mm = None
    display_res_dpi =  None
    display_diag_in = None
    
def update_parameters(parameters, window):
    p=parameters
    p.screen_host = window.TKroot.tk.call('winfo', 'server', window.TKroot)
    p.screen_width_px = window.TKroot.tk.call('winfo', 'screenwidth', window.TKroot)
    p.screen_height_px = window.TKroot.tk.call('winfo', 'screenheight', window.TKroot)
    p.display_width_mm = window.TKroot.tk.call('winfo', 'screenmmwidth', window.TKroot)
    p.display_height_mm = window.TKroot.tk.call('winfo', 'screenmmheight', window.TKroot)
    if not p.display_diag_in:
        p.display_diag_in = math.sqrt(p.display_width_mm**2 + p.display_height_mm**2)/MM_PER_INCH
    if p.screen_scaling == None:    
        p.screen_scaling = window.TKroot.tk.call('tk', 'scaling')
    if not p.screen_scaling:
        p.display_res_dpi =  math.sqrt(p.screen_width_px**2 + p.screen_height_px**2)/p.display_diag_in
        p.screen_scaling = p.display_res_dpi/GUI_REF_DPI
    else:
        p.display_res_dpi =  p.screen_width_px/(p.display_width_mm/MM_PER_INCH)

def create_layout():
    layout = [
        [sg.Text('Python version:\t\t'+'.'.join(str(x) for x in sg.sys.version_info), size=GUI_TEXT_SIZE)],      
        [sg.Text('PySimpleGUI version:\t'+sg.version, size=GUI_TEXT_SIZE)],
        [sg.Text('Tkinter version:\t'+sg.tclversion_detailed, size=GUI_TEXT_SIZE)],
        [sg.Text('', key='-TEXT1-', size=GUI_TEXT_SIZE)],
        [sg.HorizontalSeparator()],
        [sg.Text('', key='-TEXT2-', size=GUI_TEXT_SIZE)],
        [sg.Text('', key='-TEXT3-', size=GUI_TEXT_SIZE)],
        [   sg.Text('Screen scaling:\t\t[ratio]', size=(31,1)),
            sg.Input('0', key='-SCALING-', size=(5,1), pad=(0,0)),
            sg.Button('Update', key='-UPDATE_SCALING-'),
        ],
        [sg.Text('', key='-TEXT4-', size=GUI_TEXT_SIZE)],
        [sg.Text('', key='-TEXT5-', size=GUI_TEXT_SIZE)],
        [sg.Text('', key='-TEXT6-', size=GUI_TEXT_SIZE)],
        [   sg.Text('Display diagonal:\t[inch]', size=(31,1)),
            sg.Input('0', key='-DIAGONAL-', size=(5,1), pad=(0,0)),
            sg.Button('Update', key='-UPDATE_DIAGONAL-'),
        ],
    ]
    return layout

def update_view(window, parameters):
    window['-TEXT1-'].update('Tkinter platform:\t%s'%parameters.screen_host)
    window['-TEXT2-'].update('Screen width:\t\t[pixel]\t{:d}'.format(parameters.screen_width_px))
    window['-TEXT3-'].update('Screen heigth:\t\t[pixel]\t{:d}'.format(parameters.screen_height_px))
    window['-SCALING-'].update(value='{:.3f}'.format(parameters.screen_scaling))
    window['-TEXT4-'].update('Display resolution:\t[dpi]\t{:.1f}'.format(parameters.display_res_dpi))
    window['-TEXT5-'].update('Display width:\t\t[mm]\t{:d}'.format(parameters.display_width_mm))
    window['-TEXT6-'].update('Display heigth:\t\t[mm]\t{:d}'.format(parameters.display_height_mm))
    window['-DIAGONAL-'].update(value='{:.2f}'.format(parameters.display_diag_in))

def create_window(layout, scaling=None):
    # Create invisible window with no layout
    window = sg.Window(GUI_TITLE, [[]], alpha_channel=0, finalize=True)
    # Apply scaling then add layout
    if scaling: 
        window.TKroot.tk.call('tk', 'scaling', scaling)
    window.extend_layout(window, layout)
    window.refresh()
    # Move position to center according to final size
    window.move(
        window.get_screen_size()[0]//2-window.size[0]//2,
        window.get_screen_size()[1]//2-window.size[1]//2)
    window.refresh()
    # Show window and return
    window.set_alpha(1)   
    return window

window = create_window(create_layout())
parameters = Parameters()
update_parameters(parameters, window)
update_view(window, parameters)
    
# Event Loop
while True:
    event, values = window.read(timeout=500)
    if event == sg.WIN_CLOSED:
        break
    elif event == '-UPDATE_DIAGONAL-':
        parameters.display_diag_in = float(window['-DIAGONAL-'].get())
        parameters.screen_scaling = 0
        update_parameters(parameters, window)
    elif event == '-UPDATE_SCALING-':
        parameters.screen_scaling = float(window['-SCALING-'].get())
        parameters.display_diag_in = 0
    if event in ('-UPDATE_DIAGONAL-', '-UPDATE_SCALING-'):   
        window.close()
        del window
        window = create_window(create_layout(), parameters.screen_scaling)
        update_parameters(parameters, window)
        update_view(window, parameters)     
window.close()
