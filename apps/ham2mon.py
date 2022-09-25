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
    freq_correction = PARSER.freq_correction
    audio_bps = PARSER.audio_bps
    scanner = scnr.Scanner(ask_samp_rate, num_demod, type_demod, hw_args,
                           freq_correction, record, lockout_file_name,
                           priority_file_name, play, audio_bps)

    # Set the paramaters
    scanner.set_center_freq(PARSER.center_freq)
    scanner.set_gain(PARSER.gain_db)
    scanner.set_if_gain(PARSER.if_gain_db)
    scanner.set_bb_gain(PARSER.bb_gain_db)
    scanner.set_squelch(PARSER.squelch_db)
    scanner.set_volume(PARSER.volume_db)
    scanner.set_threshold(PARSER.threshold_db)

    # Get the initial settings for GUI
    rxwin.center_freq = scanner.center_freq
    rxwin.samp_rate = scanner.samp_rate
    rxwin.gain_db = scanner.gain_db
    rxwin.if_gain_db = scanner.if_gain_db
    rxwin.bb_gain_db = scanner.bb_gain_db
    rxwin.squelch_db = scanner.squelch_db
    rxwin.volume_db = scanner.volume_db
    rxwin.record = scanner.record
    rxwin.type_demod = type_demod
    rxwin.lockout_file_name = scanner.lockout_file_name
    rxwin.priority_file_name = scanner.priority_file_name

    specwin.threshold_db = scanner.threshold_db

    while 1:
        # No need to go faster than 10 Hz rate of GNU Radio probe
        time.sleep(0.1)

        # Initiate a scan cycle
        scanner.scan_cycle()

        # Update the spectrum, channel, and rx displays
        specwin.draw_spectrum(scanner.spectrum)
        chanwin.draw_channels(scanner.gui_tuned_channels)
        lockoutwin.draw_channels(scanner.gui_lockout_channels)
        rxwin.draw_rx()

        # Update physical screen
        curses.doupdate()

        # Get keystroke
        keyb = screen.getch()

        # Send keystroke to spectrum window and update scanner if True
        if specwin.proc_keyb(keyb):
            scanner.set_threshold(specwin.threshold_db)

        # Send keystroke to RX window and update scanner if True
        if rxwin.proc_keyb_hard(keyb):
            # Set and update frequency
            scanner.set_center_freq(rxwin.center_freq)
            rxwin.center_freq = scanner.center_freq

        if rxwin.proc_keyb_soft(keyb):
            # Set and update RF gain
            scanner.set_gain(rxwin.gain_db)
            rxwin.gain_db = scanner.gain_db
            # Set and update IF gain
            scanner.set_if_gain(rxwin.if_gain_db)
            rxwin.if_gain_db = scanner.if_gain_db
            # Set and update BB gain
            scanner.set_bb_gain(rxwin.bb_gain_db)
            rxwin.bb_gain_db = scanner.bb_gain_db
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
        print(err)
        print("RuntimeError: SDR hardware not detected or insufficient USB permissions. Try running as root.")
        print("")

