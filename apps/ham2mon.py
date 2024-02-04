#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  3 13:38:36 2015

@author: madengr
"""

import scanner as scnr
import curses
import cursesgui
import parser
import time
import errors as err
import traceback
import sys
import os
from datetime import datetime

def print_custom_error_message():
    exc_type, exc_value, exc_tb = sys.exc_info()
    stack_summary = traceback.extract_tb(exc_tb)
    end = stack_summary[-1]

    err_type = type(exc_value).__name__
    err_msg = str(exc_value)
    date = datetime.strftime(datetime.now(), "%B %d, %Y at precisely %I:%M %p")

    print(f"On {date}, a {err_type} occured in {end.filename} inside {end.name} on line {end.lineno} with the error message: {err_msg}.")
    print(f"The following line of code is responsible: {end.line!r}")
    print("Please make a note of it.")
    print("")

def main(screen):
    """Start scanner with GUI interface

    Initialize and set up screen
    Create windows
    Create scanner object
    Executes scan cycles
    Update windows
    Process keyboard strokes
    """
    # pylint: disable=too-many-statements
    # pylint: disable-msg=R0914

    # Use the curses.wrapper() to crash cleanly
    # Note the screen object is passed from the wrapper()
    # http://stackoverflow.com/questions/9854511/python-curses-dilemma
    # The issue is the debuuger won't work with the wrapper()
    # Nor does the python optiosn parser
    # So enable the next 2 lines and don't pass screen to main()
    #screen = curses.initscr()
    #curses.start_color()

    # Setup the screen
    cursesgui.setup_screen(screen)

    # Create windows
    specwin = cursesgui.SpectrumWindow(screen)
    chanwin = cursesgui.ChannelWindow(screen)
    lockoutwin = cursesgui.LockoutWindow(screen)
    rxwin = cursesgui.RxWindow(screen)

    # Create scanner object
    ask_samp_rate = PARSER.ask_samp_rate
    num_demod = PARSER.num_demod
    type_demod = PARSER.type_demod
    hw_args = PARSER.hw_args
    record = PARSER.record
    play = PARSER.play
    lockout_file_name = PARSER.lockout_file_name
    priority_file_name = PARSER.priority_file_name
    channel_log_file_name = PARSER.channel_log_file_name
    channel_log_timeout = PARSER.channel_log_timeout
    freq_correction = PARSER.freq_correction
    audio_bps = PARSER.audio_bps
    max_demod_length = PARSER.max_demod_length
    channel_spacing = PARSER.channel_spacing
    min_file_size = PARSER.min_file_size
    center_freq = PARSER.center_freq
    freq_low = PARSER.freq_low
    freq_high = PARSER.freq_high

    scanner = scnr.Scanner(ask_samp_rate, num_demod, type_demod, hw_args,
                           freq_correction, record, lockout_file_name,
                           priority_file_name, channel_log_file_name, channel_log_timeout,
                           play, audio_bps, max_demod_length, channel_spacing, min_file_size,
                           center_freq, freq_low, freq_high)

    # Set the paramaters
    scanner.set_center_freq(center_freq)
    
    scanner.set_squelch(PARSER.squelch_db)
    scanner.set_volume(PARSER.volume_db)
    scanner.set_threshold(PARSER.threshold_db)

    rxwin.gains = scanner.filter_and_set_gains(PARSER.gains)

    # Get the initial settings for GUI
    rxwin.center_freq = scanner.center_freq
    rxwin.min_freq = scanner.min_freq
    rxwin.max_freq = scanner.max_freq
    rxwin.freq_low = scanner.freq_low
    rxwin.freq_high = scanner.freq_high
    rxwin.samp_rate = scanner.samp_rate
    rxwin.squelch_db = scanner.squelch_db
    rxwin.volume_db = scanner.volume_db
    rxwin.record = scanner.record
    rxwin.type_demod = type_demod
    rxwin.lockout_file_name = scanner.lockout_file_name
    rxwin.priority_file_name = scanner.priority_file_name
    rxwin.channel_log_file_name = scanner.channel_log_file_name
    rxwin.channel_log_timeout = scanner.channel_log_timeout
    if (rxwin.channel_log_file_name != ""):
        rxwin.log_mode = "file"
    else:
        rxwin.log_mode = "none"

    specwin.max_db = PARSER.max_db
    specwin.min_db = PARSER.min_db
    specwin.threshold_db = scanner.threshold_db

    while 1:
        # No need to go faster than 10 Hz rate of GNU Radio probe
        time.sleep(0.1)

        # Initiate a scan cycle
        scanner.scan_cycle()

        # Update the spectrum, channel, and rx displays
        specwin.draw_spectrum(scanner.spectrum)
        chanwin.draw_channels(scanner.gui_tuned_channels, scanner.gui_active_channels)
        lockoutwin.draw_channels(scanner.gui_lockout_channels, scanner.gui_active_channels)
        rxwin.draw_rx()

        # Update physical screen
        curses.doupdate()

        # Get keystroke
        keyb = screen.getch()

        if keyb == ord('Q'):
            break

        # Send keystroke to spectrum window and update scanner if True
        if specwin.proc_keyb(keyb):
            scanner.set_threshold(specwin.threshold_db)

        # Send keystroke to RX window and update scanner if True
        if rxwin.proc_keyb_hard(keyb):
            # Set and update frequency
            scanner.set_center_freq(rxwin.center_freq)
            rxwin.center_freq = scanner.center_freq
            rxwin.min_freq = scanner.min_freq
            rxwin.max_freq = scanner.max_freq

        if rxwin.proc_keyb_soft(keyb):
            # Set all the gains
            rxwin.gains = scanner.filter_and_set_gains(rxwin.gains)
            # Set and update squelch
            scanner.set_squelch(rxwin.squelch_db)
            rxwin.squelch_db = scanner.squelch_db
            # Set and update volume
            scanner.set_volume(rxwin.volume_db)
            rxwin.volume_db = scanner.volume_db

        # Send keystroke to lockout window and update lockout channels if True
        if lockoutwin.proc_keyb_set_lockout(keyb) and rxwin.freq_entry == 'None':
            # Subtract 48 from ascii keyb value to obtain 0 - 9
            idx = keyb - 48
            scanner.add_lockout(idx)
        if lockoutwin.proc_keyb_clear_lockout(keyb):
            scanner.clear_lockout()

    # cleanup terminating all demodulators
    for demod in scanner.receiver.demodulators:
        demod.set_tuner_freq(0, 0);

if __name__ == '__main__':
    try:
        # Do this since curses wrapper won't let parser write to screen
        PARSER = parser.CLParser()
        if len(PARSER.parser_args) != 0:
            PARSER.print_help() #pylint: disable=maybe-no-member
            raise(SystemExit, 1)
        else:
            curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except RuntimeError as err:
        print("")
        print("RuntimeError: SDR hardware not detected or insufficient USB permissions. Try running as root.")
        print("")
        print("RuntimeError: {err=}, {type(err)=}")
        print("")
        print(traceback.format_exc)
        print(sys.exc_info()[2])
        print("")

        print_custom_error_message()

    except err.LogError:
        print("")
        print("LogError: database logging not active, to be expanded.")
        print("")
        print(traceback.format_exc)
        print(sys.exc_info()[2])
        print("")

        print_custom_error_message()

    except OSError as err:
        print("")
        print("OS error: {0}".format(err))
        print("")
        print(traceback.format_exc)
        print(sys.exc_info()[2])
        print("")

        print_custom_error_message()

        #exc_type, exc_obj, exc_tb = sys.exc_info()
        #fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #print(exc_type, fname, exc_tb.tb_lineno)

    except BaseException as err:
        print("")
        print("Unexpected: {err=}, {type(err)=}", err, type(err))
        print("")
        print(traceback.format_exc)
        print(sys.exc_info()[2])
        print("")

        print_custom_error_message()

        #exc_type, exc_obj, exc_tb = sys.exc_info()
        #fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #print(exc_type, fname, exc_tb.tb_lineno)

    finally:
        # --- Cleanup on exit ---
        curses.echo()
        curses.nocbreak()
        curses.endwin()

