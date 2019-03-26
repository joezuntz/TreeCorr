# Copyright (c) 2003-2015 by Mike Jarvis
#
# TreeCorr is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.

"""
.. module:: binnedcorr3
"""

import math
import numpy as np
import sys
import coord
import treecorr

class BinnedCorr3(object):
    """This class stores the results of a 3-point correlation calculation, along with some
    ancillary data.

    This is a base class that is not intended to be constructed directly.  But it has a few
    helper functions that derived classes can use to help perform their calculations.  See
    the derived classes for more details:

    - :class:`~treecorr.NNNCorrelation` handles count-count-count correlation functions
    - :class:`~treecorr.KKKCorrelation` handles kappa-kappa-kappa correlation functions
    - :class:`~treecorr.GGGCorrelation` handles gamma-gamma-gamma correlation functions

    Three-point correlations are a bit more complicated than two-point, since the data need
    to be binned in triangles, not just the separation between two points.  We characterize the
    triangles according to the following three parameters based on the three side lenghts
    of the triangle with d1 >= d2 >= d3.

    .. math::
        r &= d2 \\\\
        u &= \\frac{d3}{d2} \\\\
        v &= \\pm \\frac{(d1 - d2)}{d3} \\\\

    The orientation of the triangle is specified by the sign of v.
    Positive v triangles have the three sides d1,d2,d3 in counter-clockwise orientation.
    Negative v triangles have the three sides d1,d2,d3 in clockwise orientation.

    The constructor for all derived classes take a config dict as the first argument,
    since this is often how we keep track of parameters, but if you don't want to
    use one or if you want to change some parameters from what are in a config dict,
    then you can use normal kwargs, which take precedence over anything in the config dict.

    There are only two implemented definitions for the distance between two points for
    three-point corretions:

        - 'Euclidean' = straight line Euclidean distance between two points.  For spherical
          coordinates (ra,dec without r), this is the chord distance between points on the
          unit sphere.
        - 'Arc' = the true great circle distance for spherical coordinates.

    Similarly, we have so far only implemented one binning type for three-point correlations.

        - 'Log' - logarithmic binning in the distance.  The bin steps will be uniform in
          log(r) from log(min_sep) .. log(max_sep). The u and v values  are binned linearly.


    :param config:      The configuration dict which defines attributes about how to read the file.
                        Any kwargs that are not those listed here will be added to the config,
                        so you can even omit the config dict and just enter all parameters you
                        want as kwargs.  (default: None)
    :param logger:      If desired, a logger object for logging. (default: None, in which case
                        one will be built according to the config dict's verbose level.)

    The following parameters may be given either in the config dict or as a named kwarg:

    :param nbins:       How many bins to use for the r binning. (Exactly three of nbins, bin_size,
                        min_sep, max_sep are required. If nbins is not given, it will be
                        calculated from the values of the other three, rounding up to the next
                        highest integer. In this case, max_sep will be readjusted to account for
                        this rounding up.)
    :param bin_size:    The width of the bins in log(separation). (Exactly three of nbins,
                        bin_size, min_sep, max_sep are required.  If bin_size is not given, it will
                        be calculated from the values of the other three.)
    :param min_sep:     The minimum separation in units of sep_units, if relevant. (Exactly three
                        of nbins, bin_size, min_sep, max_sep are required.  If min_sep is not
                        given, it will be calculated from the values of the other three.)
    :param max_sep:     The maximum separation in units of sep_units, if relevant. (Exactly three
                        of nbins, bin_size, min_sep, max_sep are required.  If max_sep is not
                        given, it will be calculated from the values of the other three.  If nbins
                        is not given, then max_sep will be adjusted as needed to allow nbins to be
                        an integer value.)

    :param sep_units:   The units to use for the separation values, given as a string.  This
                        includes both min_sep and max_sep above, as well as the units of the
                        output distance values.  Valid options are arcsec, arcmin, degrees, hours,
                        radians.  (default: radians if angular units make sense, but for 3-d
                        or flat 2-d positions, the default will just match the units of x,y[,z]
                        coordinates)
    :param bin_slop:    How much slop to allow in the placement of pairs in the bins.
                        If bin_slop = 1, then the bin into which a particular pair is placed may
                        be incorrect by at most 1.0 bin widths.  (default: None, which means to
                        use bin_slop=1 if bin_size <= 0.1, or 0.1/bin_size if bin_size > 0.1.
                        This mean the error will be at most 0.1 in log(sep), which has been found
                        to yield good results for most application.

    :param nubins:      Analogous to nbins for the u direction.  (The default is to calculate from
                        ubin_size = binsize, min_u = 0, max_u = 1, but this can be overridden by
                        specifying up to 3 of these four parametes.)
    :param ubin_size:   Analogous to bin_size for the u direction. (default: bin_size)
    :param min_u:       Analogous to min_sep for the u direction. (default: 0)
    :param max_u:       Analogous to max_sep for the u direction. (default: 1)

    :param nvbins:      Analogous to nbins for the v direction.  (The default is to calculate from
                        vbin_size = binsize, min_v = -1, max_v = 1, but this can be overridden by
                        specifying up to 3 of these four parametes.)
    :param vbin_size:   Analogous to bin_size for the v direction. (default: bin_size)
    :param min_v:       Analogous to min_sep for the v direction. (default: -1)
    :param max_v:       Analogous to max_sep for the v direction. (default: 1)

    :param brute:       Whether to use the "brute force" algorithm.  (default: False) Options are:

                        - False (the default): Stop at non-leaf cells whenever the error in the
                          separation is compatible with the given bin_slop.
                        - True: Go to the leaves for all catalogs.

                        (The number options allowed for 2pt correlations are not enabled here.)

    :param verbose:     If no logger is provided, this will optionally specify a logging level to
                        use:

                        - 0 means no logging output (default)
                        - 1 means to output warnings only
                        - 2 means to output various progress information
                        - 3 means to output extensive debugging information

    :param log_file:    If no logger is provided, this will specify a file to write the logging
                        output.  (default: None; i.e. output to standard output)
    :param output_dots: Whether to output progress dots during the calcualtion of the correlation
                        function. (default: False unless verbose is given and >= 2, in which case
                        True)

    :param split_method: How to split the cells in the tree when building the tree structure.
                        Options are:

                        - mean: Use the arithmetic mean of the coordinate being split. (default)
                        - median: Use the median of the coordinate being split.
                        - middle: Use the middle of the range; i.e. the average of the minimum and
                          maximum value.
                        - random: Use a random point somewhere in the middle two quartiles of the
                          range.

    :param min_top:     The minimum number of top layers to use when setting up the field.
                        (default: 3)
    :param max_top:     The maximum number of top layers to use when setting up the field.
                        The top-level cells are the cells where each calculation job starts.
                        There will typically be of order 2^max_top top-level cells. (default: 10)
    :param precision:   The precision to use for the output values. This should be an integer,
                        which specifies how many digits to write. (default: 4)

    :param metric:      Which metric to use for distance measurements.  Options are given above.
                        (default: 'Euclidean')
    :param bin_type:    What type of binning should be used. The only valid option is 'Log'.
                        (default: 'Log')
    :param min_rpar:    For the 'Rperp' metric, the minimum difference in Rparallel to allow
                        for pairs being included in the correlation function. (default: None)
    :param max_rpar:    For the 'Rperp' metric, the maximum difference in Rparallel to allow
                        for pairs being included in the correlation function. (default: None)
    :param period:      For the 'Periodic' metric, the period to use in the all directions.
                        (default: None)
    :param xperiod:     For the 'Periodic' metric, the period to use in the x direction.
                        (default: period)
    :param yperiod:     For the 'Periodic' metric, the period to use in the y direction.
                        (default: period)
    :param zperiod:     For the 'Periodic' metric, the period to use in the z direction.
                        (default: period)

    :param num_threads: How many OpenMP threads to use during the calculation.
                        (default: use the number of cpu cores; this value can also be given in
                        the constructor in the config dict.) Note that this won't work if the
                        system's C compiler is clang prior to version 3.7.
     """
    _valid_params = {
        'nbins' : (int, False, None, None,
                'The number of output bins to use for sep dimension.'),
        'bin_size' : (float, False, None, None,
                'The size of the output bins in log(sep).'),
        'min_sep' : (float, False, None, None,
                'The minimum separation to include in the output.'),
        'max_sep' : (float, False, None, None,
                'The maximum separation to include in the output.'),
        'sep_units' : (str, False, None, coord.AngleUnit.valid_names,
                'The units to use for min_sep and max_sep.  Also the units of the output distances'),
        'bin_slop' : (float, False, None, None,
                'The fraction of a bin width by which it is ok to let the pairs miss the correct bin.',
                'The default is to use 1 if bin_size <= 0.1, or 0.1/bin_size if bin_size > 0.1.'),
        'nubins' : (int, False, None, None,
                'The number of output bins to use for u dimension.'),
        'ubin_size' : (float, False, None, None,
                'The size of the output bins in u.'),
        'min_u' : (float, False, None, None,
                'The minimum u to include in the output.'),
        'max_u' : (float, False, None, None,
                'The maximum u to include in the output.'),
        'nvbins' : (int, False, None, None,
                'The number of output bins to use for v dimension.'),
        'vbin_size' : (float, False, None, None,
                'The size of the output bins in v.'),
        'min_v' : (float, False, None, None,
                'The minimum v to include in the output.'),
        'max_v' : (float, False, None, None,
                'The maximum v to include in the output.'),
        'brute' : (bool, False, False, [False, True],
                'Whether to use brute-force algorithm'),
        'verbose' : (int, False, 1, [0, 1, 2, 3],
                'How verbose the code should be during processing. ',
                '0 = Errors Only, 1 = Warnings, 2 = Progress, 3 = Debugging'),
        'log_file' : (str, False, None, None,
                'If desired, an output file for the logging output.',
                'The default is to write the output to stdout.'),
        'output_dots' : (bool, False, None, None,
                'Whether to output dots to the stdout during the C++-level computation.',
                'The default is True if verbose >= 2 and there is no log_file.  Else False.'),
        'split_method' : (str, False, 'mean', ['mean', 'median', 'middle', 'random'],
                'Which method to use for splitting cells.'),
        'min_top' : (int, False, 3, None,
                'The minimum number of top layers to use when setting up the field.'),
        'max_top' : (int, False, 10, None,
                'The maximum number of top layers to use when setting up the field.'),
        'precision' : (int, False, 4, None,
                'The number of digits after the decimal in the output.'),
        'num_threads' : (int, False, None, None,
                'How many threads should be used. num_threads <= 0 means auto based on num cores.'),
        'metric': (str, False, 'Euclidean', ['Euclidean', 'Arc'],
                'Which metric to use for the distance measurements'),
        'bin_type': (str, False, 'Log', ['Log'],
                'Which type of binning should be used'),
        'min_rpar': (float, False, None, None,
                'The minimum difference in Rparallel for pairs to include'),
        'max_rpar': (float, False, None, None,
                'The maximum difference in Rparallel for pairs to include'),
        'period': (float, False, None, None,
                'The period to use for all directions for the Periodic metric'),
        'xperiod': (float, False, None, None,
                'The period to use for the x direction for the Periodic metric'),
        'yperiod': (float, False, None, None,
                'The period to use for the y direction for the Periodic metric'),
        'zperiod': (float, False, None, None,
                'The period to use for the z direction for the Periodic metric'),
    }

    def __init__(self, config=None, logger=None, **kwargs):
        self.config = treecorr.config.merge_config(config,kwargs,BinnedCorr3._valid_params)
        if logger is None:
            self.logger = treecorr.config.setup_logger(
                    treecorr.config.get(self.config,'verbose',int,0),
                    self.config.get('log_file',None))
        else:
            self.logger = logger

        if 'output_dots' in self.config:
            self.output_dots = treecorr.config.get(self.config,'output_dots',bool)
        else:
            self.output_dots = treecorr.config.get(self.config,'verbose',int,0) >= 2

        self.bin_type = self.config.get('bin_type', None)
        if self.bin_type != 'Log':
            raise ValueError("Invalid bin_type %s"%self.bin_type)
        self._bintype = treecorr._lib.Log

        self.sep_units = self.config.get('sep_units','')
        self._sep_units = treecorr.config.get(self.config,'sep_units',str,'radians')
        self._log_sep_units = math.log(self._sep_units)
        if 'nbins' not in self.config:
            if 'max_sep' not in self.config:
                raise AttributeError("Missing required parameter max_sep")
            if 'min_sep' not in self.config:
                raise AttributeError("Missing required parameter min_sep")
            if 'bin_size' not in self.config:
                raise AttributeError("Missing required parameter bin_size")
            self.min_sep = float(self.config['min_sep'])
            self.max_sep = float(self.config['max_sep'])
            if self.min_sep >= self.max_sep:
                raise ValueError("max_sep must be larger than min_sep")
            self.bin_size = float(self.config['bin_size'])
            self.nbins = int(math.ceil(math.log(self.max_sep/self.min_sep)/self.bin_size))
            # Update max_sep given this value of nbins
            self.max_sep = math.exp(self.nbins*self.bin_size)*self.min_sep
        elif 'bin_size' not in self.config:
            if 'max_sep' not in self.config:
                raise AttributeError("Missing required parameter max_sep")
            if 'min_sep' not in self.config:
                raise AttributeError("Missing required parameter min_sep")
            self.min_sep = float(self.config['min_sep'])
            self.max_sep = float(self.config['max_sep'])
            if self.min_sep >= self.max_sep:
                raise ValueError("max_sep must be larger than min_sep")
            self.nbins = int(self.config['nbins'])
            self.bin_size = math.log(self.max_sep/self.min_sep)/self.nbins
        elif 'max_sep' not in self.config:
            if 'min_sep' not in self.config:
                raise AttributeError("Missing required parameter min_sep")
            self.min_sep = float(self.config['min_sep'])
            self.nbins = int(self.config['nbins'])
            self.bin_size = float(self.config['bin_size'])
            self.max_sep = math.exp(self.nbins*self.bin_size)*self.min_sep
        else:
            if 'min_sep' in self.config:
                raise AttributeError("Only 3 of min_sep, max_sep, bin_size, nbins are allowed.")
            self.max_sep = float(self.config['max_sep'])
            self.nbins = int(self.config['nbins'])
            self.bin_size = float(self.config['bin_size'])
            self.min_sep = self.max_sep*math.exp(-self.nbins*self.bin_size)
        if self.sep_units == '':
            self.logger.info("r: nbins = %d, min,max sep = %g..%g, bin_size = %g",
                             self.nbins,self.min_sep,self.max_sep,self.bin_size)
        else:
            self.logger.info("r: nbins = %d, min,max sep = %g..%g %s, bin_size = %g",
                             self.nbins,self.min_sep/self._sep_units,self.max_sep/self._sep_units,
                             self.sep_units,self.bin_size)
        # The underscore-prefixed names are in natural units (radians for angles)
        self._min_sep = self.min_sep * self._sep_units
        self._max_sep = self.max_sep * self._sep_units
        self._bin_size = self.bin_size  # There is not Linear, but if I add it, need to apply
                                        # units to _bin_size in that case as well.

        self.min_u = float(self.config.get('min_u', 0.))
        self.max_u = float(self.config.get('max_u', 1.))
        if self.min_u >= self.max_u:
            raise ValueError("max_u must be larger than min_u")
        self.ubin_size = float(self.config.get('ubin_size', self.bin_size))
        if 'nubins' not in self.config:
            self.nubins = int(math.ceil((self.max_u-self.min_u-1.e-10)/self.ubin_size))
        elif 'max_u' in self.config and 'min_u' in self.config and 'ubin_size' in self.config:
                raise AttributeError("Only 3 of min_u, max_u, ubin_size, nubins are allowed.")
        else:
            self.nubins = self.config['nubins']
            # Allow min or max u to be implicit from nubins and ubin_size
            if 'ubin_size' in self.config:
                if 'min_u' not in self.config:
                    self.min_u = max(self.max_u - self.nubins * self.ubin_size, 0.)
                if 'max_u' not in self.config:
                    self.max_u = min(self.min_u + self.nubins * self.ubin_size, 1.)
        # Adjust ubin_size given the other values
        self.ubin_size = (self.max_u-self.min_u)/self.nubins
        self.logger.info("u: nbins = %d, min,max = %g..%g, bin_size = %g",
                         self.nubins,self.min_u,self.max_u,self.ubin_size)

        self.min_v = float(self.config.get('min_v', -1.))
        self.max_v = float(self.config.get('max_v', 1.))
        if self.min_v >= self.max_v:
            raise ValueError("max_v must be larger than min_v")
        self.vbin_size = float(self.config.get('vbin_size', self.bin_size))
        if 'nvbins' not in self.config:
            self.nvbins = int(math.ceil((self.max_v-self.min_v-1.e-10)/self.vbin_size))
            if 'min_v' not in self.config and 'max_v' not in self.config:
                # Make sure nvbins is even when range is implicitly [-1,1]
                self.nvbins += self.nvbins%2
        elif 'max_v' in self.config and 'min_v' in self.config and 'vbin_size' in self.config:
                raise AttributeError("Only 3 of min_v, max_v, vbin_size, nvbins are allowed.")
        else:
            self.nvbins = self.config['nvbins']
            # Allow min or max v to be implicit from nvbins and vbin_size
            if 'vbin_size' in self.config:
                if 'min_v' not in self.config and 'max_v' not in self.config:
                    self.max_v = min(self.nvbins * self.vbin_size / 2., 1.)
                    self.min_v = -self.max_v
                if 'min_v' not in self.config:
                    self.min_v = max(self.max_v - self.nvbins * self.vbin_size, -1.)
                if 'max_v' not in self.config:
                    self.max_v = min(self.min_v + self.nvbins * self.vbin_size, 1.)
        # Adjust vbin_size given the other values
        self.vbin_size = (self.max_v-self.min_v)/self.nvbins
        self.logger.info("v: nbins = %d, min,max = %g..%g, bin_size = %g",
                         self.nvbins,self.min_v,self.max_v,self.vbin_size)

        self.split_method = self.config.get('split_method','mean')
        if self.split_method not in ['middle', 'median', 'mean', 'random']:
            raise ValueError("Invalid split_method %s"%self.split_method)
        self.logger.debug("Using split_method = %s",self.split_method)

        self.min_top = treecorr.config.get(self.config,'min_top',int,3)
        self.max_top = treecorr.config.get(self.config,'max_top',int,10)

        self.bin_slop = treecorr.config.get(self.config,'bin_slop',float,-1.0)
        if self.bin_slop < 0.0:
            if self.bin_size <= 0.1:
                self.bin_slop = 1.0
                self.b = self.bin_size
            else:
                self.bin_slop = 0.1/self.bin_size  # The stored bin_slop corresponds to lnr bins.
                self.b = 0.1
            if self.ubin_size <= 0.1:
                self.bu = self.ubin_size
            else:
                self.bu = 0.1
            if self.vbin_size <= 0.1:
                self.bv = self.vbin_size
            else:
                self.bv = 0.1
        else:
            self.b = self.bin_size * self.bin_slop
            self.bu = self.ubin_size * self.bin_slop
            self.bv = self.vbin_size * self.bin_slop

        if self.b > 0.100001:  # Add some numerical slop
            self.logger.warning(
                    "Using bin_slop = %g, bin_size = %g\n"%(self.bin_slop,self.bin_size)+
                    "The b parameter is bin_slop * bin_size = %g"%(self.b)+
                    "  bu = %g, bv = %g\n"%(self.bu,self.bv)+
                    "It is generally recommended to use b <= 0.1 for most applications.\n"+
                    "Larger values of this b parameter may result in significant inaccuracies.")
        else:
            self.logger.debug("Using bin_slop = %g, b = %g, bu = %g, bv = %g",
                              self.bin_slop,self.b,self.bu,self.bv)

        # This makes nbins evenly spaced entries in log(r) starting with 0 with step bin_size
        self.logr1d = np.linspace(start=0, stop=self.nbins*self.bin_size,
                                   num=self.nbins, endpoint=False)
        # Offset by the position of the center of the first bin.
        self.logr1d += math.log(self.min_sep) + 0.5*self.bin_size

        self.u1d = np.linspace(start=0, stop=self.nubins*self.ubin_size,
                                  num=self.nubins, endpoint=False)
        self.u1d += self.min_u + 0.5*self.ubin_size

        self.v1d = np.linspace(start=0, stop=self.nvbins*self.vbin_size,
                                  num=self.nvbins, endpoint=False)
        self.v1d += self.min_v + 0.5*self.vbin_size

        shape = (self.nbins, self.nubins, self.nvbins)
        self.logr = np.tile(self.logr1d[:, np.newaxis, np.newaxis],
                               (1, self.nubins, self.nvbins))
        self.u = np.tile(self.u1d[np.newaxis, :, np.newaxis],
                            (self.nbins, 1, self.nvbins))
        self.v = np.tile(self.v1d[np.newaxis, np.newaxis, :],
                            (self.nbins, self.nubins, 1))
        self.rnom = np.exp(self.logr)
        self.brute = treecorr.config.get(self.config,'brute',bool,False)
        if self.brute:
            self.logger.info("Doing brute force calculation.",)
        self.coords = None
        self.metric = None
        self.min_rpar = treecorr.config.get(self.config,'min_rpar',float,-sys.float_info.max)
        self.max_rpar = treecorr.config.get(self.config,'max_rpar',float,sys.float_info.max)
        period = treecorr.config.get(self.config,'period',float,0)
        self.xperiod = treecorr.config.get(self.config,'xperiod',float,period)
        self.yperiod = treecorr.config.get(self.config,'yperiod',float,period)
        self.zperiod = treecorr.config.get(self.config,'zperiod',float,period)

    def _process_all_auto(self, cat1, metric, num_threads):
        # I'm not sure which of these is more intuitive, but both are correct...
        if True:
            for c1 in cat1:
                self.process_auto(c1, metric, num_threads)
                for c2 in cat1:
                    if c2 is not c1:
                        self.process_cross(c1,c1,c2, metric, num_threads)
                        self.process_cross(c1,c2,c1, metric, num_threads)
                        self.process_cross(c2,c1,c1, metric, num_threads)
                        for c3 in cat1:
                            if c3 is not c1 and c3 is not c2:
                                self.process_cross(c1,c2,c3, metric, num_threads)
        else: # pragma: no cover
            for i,c1 in enumerate(cat1):
                self.process_auto(c1)
                for j,c2 in enumerate(cat1[i+1:]):
                    self.process_cross(c1,c1,c2, metric, num_threads)
                    self.process_cross(c1,c2,c1, metric, num_threads)
                    self.process_cross(c2,c1,c1, metric, num_threads)
                    self.process_cross(c1,c2,c2, metric, num_threads)
                    self.process_cross(c2,c1,c2, metric, num_threads)
                    self.process_cross(c2,c2,c1, metric, num_threads)
                    for c3 in cat1[i+j+1:]:
                        self.process_cross(c1,c2,c3, metric, num_threads)
                        self.process_cross(c1,c3,c2, metric, num_threads)
                        self.process_cross(c2,c1,c3, metric, num_threads)
                        self.process_cross(c2,c3,c1, metric, num_threads)
                        self.process_cross(c3,c1,c2, metric, num_threads)
                        self.process_cross(c3,c2,c1, metric, num_threads)

    # These are not actually implemented yet.
    def _process_all_cross21(self, cat1, cat2, metric, num_threads): # pragma: no cover
        for c1 in cat1:
            for c2 in cat2:
                self.process_cross(c1,c1,c2, metric, num_threads)
            for c3 in cat1:
                if c3 is not c1:
                    self.process_cross(c1,c3,c2, metric, num_threads)
                    self.process_cross(c3,c1,c2, metric, num_threads)

    def _process_all_cross(self, cat1, cat2, cat3, metric, num_threads):
        for c1 in cat1:
            for c2 in cat2:
                for c3 in cat3:
                    self.process_cross(c1,c2,c3, metric, num_threads)

    def _set_num_threads(self, num_threads):
        if num_threads is None:
            num_threads = self.config.get('num_threads',None)
        if num_threads is None:
            self.logger.debug('Set num_threads automatically from ncpu')
        else:
            self.logger.debug('Set num_threads = %d',num_threads)
        treecorr.set_omp_threads(num_threads, self.logger)

    def _set_metric(self, metric, coords1, coords2=None, coords3=None):
        if metric is None:
            metric = treecorr.config.get(self.config,'metric',str,'Euclidean')
        coords, metric = treecorr.util.parse_metric(metric, coords1, coords2, coords3)
        if self.coords != None or self.metric != None:
            if coords != self.coords:
                self.logger.warning("Detected a change in catalog coordinate systems. "+
                                    "This probably doesn't make sense!")
            if metric != self.metric:
                self.logger.warning("Detected a change in metric. "+
                                    "This probably doesn't make sense!")
        if metric == 'Periodic':
            if self.xperiod == 0 or self.yperiod == 0 or (coords=='3d' and self.zperiod == 0):
                raise ValueError("Periodic metric requires setting the period to use.")
        else:
            if self.xperiod != 0 or self.yperiod != 0 or self.zperiod != 0:
                raise ValueError("period options are not valid for %s metric."%metric)
        self.coords = coords
        self.metric = metric
        self._coords = treecorr.util.coord_enum(coords)
        self._metric = treecorr.util.metric_enum(metric)

    def _apply_units(self, mask):
        if self.coords == 'spherical' and self.metric == 'Euclidean':
            # Then our distances are all angles.  Convert from the chord distance to a real angle.
            # L = 2 sin(theta/2)
            self.meand1[mask] = 2. * np.arcsin(self.meand1[mask]/2.)
            self.meanlogd1[mask] = np.log(2.*np.arcsin(np.exp(self.meanlogd1[mask])/2.))
            self.meand2[mask] = 2. * np.arcsin(self.meand2[mask]/2.)
            self.meanlogd2[mask] = np.log(2.*np.arcsin(np.exp(self.meanlogd2[mask])/2.))
            self.meand3[mask] = 2. * np.arcsin(self.meand3[mask]/2.)
            self.meanlogd3[mask] = np.log(2.*np.arcsin(np.exp(self.meanlogd3[mask])/2.))

        self.meand1[mask] /= self._sep_units
        self.meanlogd1[mask] -= self._log_sep_units
        self.meand2[mask] /= self._sep_units
        self.meanlogd2[mask] -= self._log_sep_units
        self.meand3[mask] /= self._sep_units
        self.meanlogd3[mask] -= self._log_sep_units

    def _get_minmax_size(self):
        if self.metric == 'Euclidean':
            # The minimum separation we care about is that of the smallest size, which is
            # min_sep * min_u.  Do the same calculation as for 2pt to get to min_size.
            b1 = min(self.b, self.bu, self.bv)
            min_size = self._min_sep * self.min_u * b1 / (2.+3.*b1)

            # This time, the maximum size is d1 * b.  d1 can be as high as 2*max_sep.
            b2 = max(self.b, self.bu, self.bv)
            max_size = 2. * self._max_sep * b2
            return min_size, max_size
        else:
            return 0., 0.

