#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Ham2Mon NBFM Receiver Flow Example
# Description: Example of GR DSP flow in receiver.py
# GNU Radio version: v3.11.0.0git-215-g9a698313

from packaging.version import Version as StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import analog
import math
from gnuradio import audio
from gnuradio import blocks
from gnuradio import fft
from gnuradio.fft import window
from gnuradio import filter
from gnuradio import gr
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio.filter import pfb
from gnuradio.qtgui import Range, GrRangeWidget
from PyQt5 import QtCore
import numpy as np
import osmosdr
import time



from gnuradio import qtgui

class nbfm_flow_example(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Ham2Mon NBFM Receiver Flow Example", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Ham2Mon NBFM Receiver Flow Example")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "nbfm_flow_example")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 1E6
        self.initial_decim = initial_decim = 5
        self.samp_ratio = samp_ratio = samp_rate/1E6
        self.final_rate = final_rate = samp_rate/initial_decim**2/int(samp_rate/1E6)
        self.variable_low_pass_filter_taps_2 = variable_low_pass_filter_taps_2 = firdes.low_pass(1.0, final_rate, 3500,500, window.WIN_HAMMING, 6.76)
        self.variable_low_pass_filter_taps_1 = variable_low_pass_filter_taps_1 = firdes.low_pass(1.0, samp_rate/25, 12.5E3,1E3, window.WIN_HAMMING, 6.76)
        self.variable_low_pass_filter_taps_0 = variable_low_pass_filter_taps_0 = firdes.low_pass(1.0, 1, 0.090,0.010, window.WIN_HAMMING, 6.76)
        self.squelch_dB = squelch_dB = -70
        self.gain_db = gain_db = 30
        self.final_decim = final_decim = int(samp_rate/1E6)
        self.file_name = file_name = "test.wav"
        self.fft_length = fft_length = 256 * int(pow(2, np.ceil(np.log(samp_ratio)/np.log(2))))
        self.demod_bb_freq = demod_bb_freq = 390E3
        self.center_freq = center_freq = 144E6

        ##################################################
        # Blocks
        ##################################################
        self._squelch_dB_range = Range(-100, 0, 5, -70, 200)
        self._squelch_dB_win = GrRangeWidget(self._squelch_dB_range, self.set_squelch_dB, "Squelch (dB)", "counter_slider", float, QtCore.Qt.Horizontal, "value")
        self.squelch_dB = self._squelch_dB_win

        self.top_grid_layout.addWidget(self._squelch_dB_win, 5, 1, 1, 3)
        for r in range(5, 6):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._gain_db_range = Range(0, 70, 1, 30, 200)
        self._gain_db_win = GrRangeWidget(self._gain_db_range, self.set_gain_db, "HW Gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal, "value")
        self.gain_db = self._gain_db_win

        self.top_grid_layout.addWidget(self._gain_db_win, 4, 1, 1, 3)
        for r in range(4, 5):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._demod_bb_freq_range = Range(-samp_rate/2, samp_rate/2, 5E3, 390E3, 200)
        self._demod_bb_freq_win = GrRangeWidget(self._demod_bb_freq_range, self.set_demod_bb_freq, "Demod BB Freq (Hz)", "counter_slider", float, QtCore.Qt.Horizontal, "value")
        self.demod_bb_freq = self._demod_bb_freq_win

        self.top_grid_layout.addWidget(self._demod_bb_freq_win, 3, 1, 1, 3)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_time_sink_x_0 = qtgui.time_sink_f(
            fft_length, #size
            samp_rate, #samp_rate
            "Averaged Spectrum", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_0.set_update_time(0.10)
        self.qtgui_time_sink_x_0.set_y_axis(-60, 40)

        self.qtgui_time_sink_x_0.set_y_label('Power', "")

        self.qtgui_time_sink_x_0.enable_tags(True)
        self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_0.enable_autoscale(False)
        self.qtgui_time_sink_x_0.enable_grid(False)
        self.qtgui_time_sink_x_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_0.enable_control_panel(False)
        self.qtgui_time_sink_x_0.enable_stem_plot(False)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_time_sink_x_0_win, 0, 1, 3, 1)
        for r in range(0, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_freq_sink_x_0_0 = qtgui.freq_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            final_rate, #bw
            "Decimated Channel", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0_0.set_y_axis((-200), (-60))
        self.qtgui_freq_sink_x_0_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0_0.enable_grid(False)
        self.qtgui_freq_sink_x_0_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0_0.set_fft_window_normalized(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_0_win, 3, 0, 3, 1)
        for r in range(3, 6):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            fft_length, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            144E6, #fc
            samp_rate, #bw
            "Spectrum", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.10)
        self.qtgui_freq_sink_x_0.set_y_axis((-120), (-20))
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(False)
        self.qtgui_freq_sink_x_0.set_fft_average(1.0)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)



        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win, 0, 0, 3, 1)
        for r in range(0, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.pfb_arb_resampler_xxx_0 = pfb.arb_resampler_fff(
            (16E3/float(final_rate/5)),
            taps=None,
            flt_size=32)
        self.pfb_arb_resampler_xxx_0.declare_sample_delay(0)
        self.osmosdr_source_0 = osmosdr.source(
            args="numchan=" + str(1) + " " + 'uhd'
        )
        self.osmosdr_source_0.set_time_unknown_pps(osmosdr.time_spec_t())
        self.osmosdr_source_0.set_sample_rate(samp_rate)
        self.osmosdr_source_0.set_center_freq(center_freq, 0)
        self.osmosdr_source_0.set_freq_corr(0, 0)
        self.osmosdr_source_0.set_dc_offset_mode(0, 0)
        self.osmosdr_source_0.set_iq_balance_mode(0, 0)
        self.osmosdr_source_0.set_gain_mode(False, 0)
        self.osmosdr_source_0.set_gain(gain_db, 0)
        self.osmosdr_source_0.set_if_gain(20, 0)
        self.osmosdr_source_0.set_bb_gain(20, 0)
        self.osmosdr_source_0.set_antenna('', 0)
        self.osmosdr_source_0.set_bandwidth((samp_rate*0.8), 0)
        self.freq_xlating_fir_filter_xxx_0 = filter.freq_xlating_fir_filter_ccc(initial_decim, variable_low_pass_filter_taps_0, demod_bb_freq, samp_rate)
        self.fir_filter_xxx_0_1 = filter.fir_filter_fff(initial_decim, variable_low_pass_filter_taps_0)
        self.fir_filter_xxx_0_1.declare_sample_delay(0)
        self.fir_filter_xxx_0_0 = filter.fir_filter_ccc((int(samp_rate/1E6)), variable_low_pass_filter_taps_0)
        self.fir_filter_xxx_0_0.declare_sample_delay(0)
        self.fir_filter_xxx_0 = filter.fir_filter_ccc(initial_decim, variable_low_pass_filter_taps_0)
        self.fir_filter_xxx_0.declare_sample_delay(0)
        self.fft_vxx_0 = fft.fft_vcc(fft_length, True, window.blackmanharris(fft_length), True, 1)
        self.blocks_wavfile_sink_0 = blocks.wavfile_sink(
            file_name,
            1,
            16000,
            blocks.FORMAT_WAV,
            blocks.FORMAT_PCM_U8,
            False
            )
        self.blocks_vector_to_stream_0 = blocks.vector_to_stream(gr.sizeof_float*1, fft_length)
        self.blocks_stream_to_vector_0 = blocks.stream_to_vector(gr.sizeof_gr_complex*1, fft_length)
        self.blocks_probe_signal_vx_0 = blocks.probe_signal_vf(fft_length)
        self.blocks_nlog10_ff_0 = blocks.nlog10_ff(10, fft_length, 0)
        self.blocks_keep_one_in_n_0 = blocks.keep_one_in_n(gr.sizeof_gr_complex*fft_length, (int(round(samp_rate/fft_length/1000))))
        self.blocks_integrate_xx_0 = blocks.integrate_ff(100, fft_length)
        self.blocks_complex_to_mag_squared_0 = blocks.complex_to_mag_squared(fft_length)
        self.audio_sink_0 = audio.sink(16000, '', True)
        self.analog_quadrature_demod_cf_0 = analog.quadrature_demod_cf(0.050)
        self.analog_pwr_squelch_xx_0_0 = analog.pwr_squelch_ff((-200), 0.1, 0, True)
        self.analog_pwr_squelch_xx_0 = analog.pwr_squelch_cc(squelch_dB, 0.1, 0, False)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_pwr_squelch_xx_0, 0), (self.analog_quadrature_demod_cf_0, 0))
        self.connect((self.analog_pwr_squelch_xx_0_0, 0), (self.blocks_wavfile_sink_0, 0))
        self.connect((self.analog_quadrature_demod_cf_0, 0), (self.fir_filter_xxx_0_1, 0))
        self.connect((self.blocks_complex_to_mag_squared_0, 0), (self.blocks_integrate_xx_0, 0))
        self.connect((self.blocks_integrate_xx_0, 0), (self.blocks_nlog10_ff_0, 0))
        self.connect((self.blocks_keep_one_in_n_0, 0), (self.fft_vxx_0, 0))
        self.connect((self.blocks_nlog10_ff_0, 0), (self.blocks_probe_signal_vx_0, 0))
        self.connect((self.blocks_nlog10_ff_0, 0), (self.blocks_vector_to_stream_0, 0))
        self.connect((self.blocks_stream_to_vector_0, 0), (self.blocks_keep_one_in_n_0, 0))
        self.connect((self.blocks_vector_to_stream_0, 0), (self.qtgui_time_sink_x_0, 0))
        self.connect((self.fft_vxx_0, 0), (self.blocks_complex_to_mag_squared_0, 0))
        self.connect((self.fir_filter_xxx_0, 0), (self.fir_filter_xxx_0_0, 0))
        self.connect((self.fir_filter_xxx_0_0, 0), (self.analog_pwr_squelch_xx_0, 0))
        self.connect((self.fir_filter_xxx_0_0, 0), (self.qtgui_freq_sink_x_0_0, 0))
        self.connect((self.fir_filter_xxx_0_1, 0), (self.pfb_arb_resampler_xxx_0, 0))
        self.connect((self.freq_xlating_fir_filter_xxx_0, 0), (self.fir_filter_xxx_0, 0))
        self.connect((self.osmosdr_source_0, 0), (self.blocks_stream_to_vector_0, 0))
        self.connect((self.osmosdr_source_0, 0), (self.freq_xlating_fir_filter_xxx_0, 0))
        self.connect((self.osmosdr_source_0, 0), (self.qtgui_freq_sink_x_0, 0))
        self.connect((self.pfb_arb_resampler_xxx_0, 0), (self.analog_pwr_squelch_xx_0_0, 0))
        self.connect((self.pfb_arb_resampler_xxx_0, 0), (self.audio_sink_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "nbfm_flow_example")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_final_decim(int(self.samp_rate/1E6))
        self.set_final_rate(self.samp_rate/self.initial_decim**2/int(self.samp_rate/1E6))
        self.set_samp_ratio(self.samp_rate/1E6)
        self.set_variable_low_pass_filter_taps_1(firdes.low_pass(1.0, self.samp_rate/25, 12.5E3, 1E3, window.WIN_HAMMING, 6.76))
        self.blocks_keep_one_in_n_0.set_n((int(round(self.samp_rate/self.fft_length/1000))))
        self.osmosdr_source_0.set_sample_rate(self.samp_rate)
        self.osmosdr_source_0.set_bandwidth((self.samp_rate*0.8), 0)
        self.qtgui_freq_sink_x_0.set_frequency_range(144E6, self.samp_rate)
        self.qtgui_time_sink_x_0.set_samp_rate(self.samp_rate)

    def get_initial_decim(self):
        return self.initial_decim

    def set_initial_decim(self, initial_decim):
        self.initial_decim = initial_decim
        self.set_final_rate(self.samp_rate/self.initial_decim**2/int(self.samp_rate/1E6))

    def get_samp_ratio(self):
        return self.samp_ratio

    def set_samp_ratio(self, samp_ratio):
        self.samp_ratio = samp_ratio
        self.set_fft_length(256 * int(pow(2, np.ceil(np.log(self.samp_ratio)/np.log(2)))))

    def get_final_rate(self):
        return self.final_rate

    def set_final_rate(self, final_rate):
        self.final_rate = final_rate
        self.set_variable_low_pass_filter_taps_2(firdes.low_pass(1.0, self.final_rate, 3500, 500, window.WIN_HAMMING, 6.76))
        self.pfb_arb_resampler_xxx_0.set_rate((16E3/float(self.final_rate/5)))
        self.qtgui_freq_sink_x_0_0.set_frequency_range(0, self.final_rate)

    def get_variable_low_pass_filter_taps_2(self):
        return self.variable_low_pass_filter_taps_2

    def set_variable_low_pass_filter_taps_2(self, variable_low_pass_filter_taps_2):
        self.variable_low_pass_filter_taps_2 = variable_low_pass_filter_taps_2

    def get_variable_low_pass_filter_taps_1(self):
        return self.variable_low_pass_filter_taps_1

    def set_variable_low_pass_filter_taps_1(self, variable_low_pass_filter_taps_1):
        self.variable_low_pass_filter_taps_1 = variable_low_pass_filter_taps_1

    def get_variable_low_pass_filter_taps_0(self):
        return self.variable_low_pass_filter_taps_0

    def set_variable_low_pass_filter_taps_0(self, variable_low_pass_filter_taps_0):
        self.variable_low_pass_filter_taps_0 = variable_low_pass_filter_taps_0
        self.fir_filter_xxx_0.set_taps(self.variable_low_pass_filter_taps_0)
        self.fir_filter_xxx_0_0.set_taps(self.variable_low_pass_filter_taps_0)
        self.fir_filter_xxx_0_1.set_taps(self.variable_low_pass_filter_taps_0)
        self.freq_xlating_fir_filter_xxx_0.set_taps(self.variable_low_pass_filter_taps_0)

    def get_squelch_dB(self):
        return self.squelch_dB

    def set_squelch_dB(self, squelch_dB):
        self.squelch_dB = squelch_dB
        self.analog_pwr_squelch_xx_0.set_threshold(self.squelch_dB)

    def get_gain_db(self):
        return self.gain_db

    def set_gain_db(self, gain_db):
        self.gain_db = gain_db
        self.osmosdr_source_0.set_gain(self.gain_db, 0)

    def get_final_decim(self):
        return self.final_decim

    def set_final_decim(self, final_decim):
        self.final_decim = final_decim

    def get_file_name(self):
        return self.file_name

    def set_file_name(self, file_name):
        self.file_name = file_name
        self.blocks_wavfile_sink_0.open(self.file_name)

    def get_fft_length(self):
        return self.fft_length

    def set_fft_length(self, fft_length):
        self.fft_length = fft_length
        self.blocks_keep_one_in_n_0.set_n((int(round(self.samp_rate/self.fft_length/1000))))

    def get_demod_bb_freq(self):
        return self.demod_bb_freq

    def set_demod_bb_freq(self, demod_bb_freq):
        self.demod_bb_freq = demod_bb_freq
        self.freq_xlating_fir_filter_xxx_0.set_center_freq(self.demod_bb_freq)

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = center_freq
        self.osmosdr_source_0.set_center_freq(self.center_freq, 0)




def main(top_block_cls=nbfm_flow_example, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
