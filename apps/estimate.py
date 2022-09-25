#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Sat Jul  4 12:09:03 2015

@author: madengr
"""

import numpy as np

def avg_freq(data):
    """Weighted average

    Takes spectrum bins and estimates frequency by weighted average

    Args:
        data (numpy.ndarray): FFT power spectrum in linear, not dB

    Returns:
        float: Fractional index into spectrum
    """

    weighted_power = 0
    sum_power = 0
    for index, sample in enumerate(data):
        weighted_power += index*sample
        sum_power += sample
    return weighted_power / float(sum_power)


def channel_estimate(spectrum, threshold):
    """Channel estimate

    Takes spectrum bins and returns channels above threshold

    Args:
        spectrum (numpy.ndarray): FFT power spectrum in linear, not dB
        threshold (float): Threshold value in linear, not dB

    Returns:
        List[float]: List of fractional indices into spectrum of channel center
    """

    # Append a zero to handle last bin above threshold
    spectrum = np.append(spectrum, np.zeros(1))

    length = len(spectrum)
    bins = []
    channels = []
    index = 0
    while index < length:
        if spectrum[index] > threshold:
            # If spectrum > threshold then append to bins list
            bins.append(spectrum[index])
            index += 1
        elif len(bins) != 0:
            # Spectrum < threshold so find average freq and append to channels
            channels.append(index - len(bins) + avg_freq(bins))
            index += 1
            bins = []
        else:
            # Spectrum < threshold so move on
            index += 1
    return channels


def main():
    """ Tests the functions in this module"""

    # Test avg_freq()
    print("Testing avg_freq()")
    data = np.array([0, 1, 1, 0])
    print("Input spectrum data is " + str(data))
    result = avg_freq(data)
    print("Average frequency is " + str(result))
    if result == 1.5:
        print("Test Pass")
    else:
        print("Test Fail")
    print("")

    # Test channel_estimate()
    print("Testing channel_estimate()")
    data = np.array([0, 1, 1, 0, 0, 1, 1, 1])
    threshold = 0.5
    print("Input spectrum data is " + str(data))
    print("Threshold is " + str(threshold))
    result = channel_estimate(data, threshold)
    print("Channels at " + str(result))
    if result == [1.5, 6.0]:
        print("Test Pass")
    else:
        print("Test Fail")
    print("")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
