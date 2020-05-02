# Copyright (c) 2003-2019 by Mike Jarvis
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
.. module:: kkcorrelation
"""

import treecorr
import numpy as np


class KKCorrelation(treecorr.BinnedCorr2):
    """This class handles the calculation and storage of a 2-point kappa-kappa correlation
    function.

    Note: while we use the term kappa (:math:`\\kappa`) here and the letter K in various places,
    in fact any scalar field will work here.  For example, you can use this to compute correlations
    of the CMB temperature fluctuations, where "kappa" would really be delta T.

    Ojects of this class holds the following attributes:

    Attributes:
        nbins:     The number of bins in logr
        bin_size:  The size of the bins in logr
        min_sep:   The minimum separation being considered
        max_sep:   The maximum separation being considered

    In addition, the following attributes are numpy arrays of length (nbins):

    Attributes:
        logr:       The nominal center of the bin in log(r) (the natural logarithm of r).
        rnom:       The nominal center of the bin converted to regular distance.
                    i.e. r = exp(logr).
        meanr:      The (weighted) mean value of r for the pairs in each bin.
                    If there are no pairs in a bin, then exp(logr) will be used instead.
        meanlogr:   The (weighted) mean value of log(r) for the pairs in each bin.
                    If there are no pairs in a bin, then logr will be used instead.
        xi:         The correlation function, :math:`\\xi(r)`
        varxi:      An estimate of the variance of :math:`\\xi`
        weight:     The total weight in each bin.
        npairs:     The number of pairs going into each bin (including pairs where one or
                    both objects have w=0).
        cov:        An estimate of the full covariance matrix.

    .. note::

        The default method for estimating the variance and covariance attributes (``varxi``,
        and ``cov``) is 'shot', which only includes the shot noise propagated into the final
        correlation.  This does not include sample variance, so it is always an underestimate of
        the actual variance.  To get better estimates, you need to set ``var_method`` to something
        else and use patches in the input catalog(s).  cf. `Covariance Estimates`.

    If **sep_units** are given (either in the config dict or as a named kwarg) then the distances
    will all be in these units.  Note however, that if you separate out the steps of the
    `process` command and use `process_auto` and/or `process_cross`, then the units will not be
    applied to **meanr** or **meanlogr** until the `finalize` function is called.

    The typical usage pattern is as follows:

        >>> kk = treecorr.KKCorrelation(config)
        >>> kk.process(cat)         # For auto-correlation.
        >>> kk.process(cat1,cat2)   # For cross-correlation.
        >>> kk.write(file_name)     # Write out to a file.
        >>> xi = kk.xi              # Or access the correlation function directly.

    Parameters:
        config (dict):  A configuration dict that can be used to pass in kwargs if desired.
                        This dict is allowed to have addition entries in addition to those listed
                        in `BinnedCorr2`, which are ignored here. (default: None)
        logger:         If desired, a logger object for logging. (default: None, in which case
                        one will be built according to the config dict's verbose level.)

    See the documentation for `BinnedCorr2` for the list of other allowed kwargs, which may be
    passed either directly or in the config dict.
    """
    def __init__(self, config=None, logger=None, **kwargs):
        treecorr.BinnedCorr2.__init__(self, config, logger, **kwargs)

        self._d1 = 2  # KData
        self._d2 = 2  # KData
        self.xi = np.zeros_like(self.rnom, dtype=float)
        self.varxi = np.zeros_like(self.rnom, dtype=float)
        self.meanr = np.zeros_like(self.rnom, dtype=float)
        self.meanlogr = np.zeros_like(self.rnom, dtype=float)
        self.weight = np.zeros_like(self.rnom, dtype=float)
        self.npairs = np.zeros_like(self.rnom, dtype=float)
        self.logger.debug('Finished building KKCorr')

    @property
    def corr(self):
        if not hasattr(self, '_corr'):
            from treecorr.util import double_ptr as dp
            self._corr = treecorr._lib.BuildCorr2(
                    self._d1, self._d2, self._bintype,
                    self._min_sep,self._max_sep,self._nbins,self._bin_size,self.b,
                    self.min_rpar, self.max_rpar, self.xperiod, self.yperiod, self.zperiod,
                    dp(self.xi), dp(None), dp(None), dp(None),
                    dp(self.meanr),dp(self.meanlogr),dp(self.weight),dp(self.npairs));
        return self._corr

    def __del__(self):
        # Using memory allocated from the C layer means we have to explicitly deallocate it
        # rather than being able to rely on the Python memory manager.
        if hasattr(self, 'corr'):
            if not treecorr._ffi._lock.locked(): # pragma: no branch
                treecorr._lib.DestroyCorr2(self.corr, self._d1, self._d2, self._bintype)

    def __eq__(self, other):
        """Return whether two KKCorrelations are equal"""
        return (isinstance(other, KKCorrelation) and
                self.nbins == other.nbins and
                self.bin_size == other.bin_size and
                self.min_sep == other.min_sep and
                self.max_sep == other.max_sep and
                self.sep_units == other.sep_units and
                self.coords == other.coords and
                self.bin_type == other.bin_type and
                self.bin_slop == other.bin_slop and
                self.min_rpar == other.min_rpar and
                self.max_rpar == other.max_rpar and
                self.xperiod == other.xperiod and
                self.yperiod == other.yperiod and
                self.zperiod == other.zperiod and
                np.array_equal(self.meanr, other.meanr) and
                np.array_equal(self.meanlogr, other.meanlogr) and
                np.array_equal(self.xi, other.xi) and
                np.array_equal(self.varxi, other.varxi) and
                np.array_equal(self.weight, other.weight) and
                np.array_equal(self.npairs, other.npairs))

    def copy(self):
        """Make a copy"""
        import copy
        return copy.deepcopy(self)

    def _copy_for_results(self):
        # Make a copy of just the things we need to keep in results.
        ret = KKCorrelation.__new__(KKCorrelation)
        ret._nbins = self._nbins
        ret.xi = self.xi.copy()
        ret.weight = self.weight.copy()
        ret.config = self.config  # not deep copy, so cheap, but makes repr work
        return ret

    def __getstate__(self):
        d = self.__dict__.copy()
        d.pop('_corr',None)
        d.pop('logger',None)  # Oh well.  This is just lost in the copy.  Can't be pickled.
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.logger = treecorr.config.setup_logger(
                treecorr.config.get(self.config,'verbose',int,1),
                self.config.get('log_file',None))

    def __repr__(self):
        return 'KKCorrelation(config=%r)'%self.config

    def process_auto(self, cat, metric=None, num_threads=None):
        """Process a single catalog, accumulating the auto-correlation.

        This accumulates the weighted sums into the bins, but does not finalize
        the calculation by dividing by the total weight at the end.  After
        calling this function as often as desired, the `finalize` command will
        finish the calculation.

        Parameters:
            cat (Catalog):      The catalog to process
            metric (str):       Which metric to use.  See `Metrics` for details.
                                (default: 'Euclidean'; this value can also be given in the
                                constructor in the config dict.)
            num_threads (int):  How many OpenMP threads to use during the calculation.
                                (default: use the number of cpu cores; this value can also be given
                                in the constructor in the config dict.)
        """
        if cat.name == '':
            self.logger.info('Starting process KK auto-correlations')
        else:
            self.logger.info('Starting process KK auto-correlations for cat %s.', cat.name)

        self._set_metric(metric, cat.coords)

        self._set_num_threads(num_threads)

        min_size, max_size = self._get_minmax_size()

        field = cat.getKField(min_size, max_size, self.split_method,
                              bool(self.brute), self.min_top, self.max_top, self.coords)

        self.logger.info('Starting %d jobs.',field.nTopLevelNodes)
        treecorr._lib.ProcessAuto2(self.corr, field.data, self.output_dots,
                                   field._d, self._coords, self._bintype, self._metric)


    def process_cross(self, cat1, cat2, metric=None, num_threads=None):
        """Process a single pair of catalogs, accumulating the cross-correlation.

        This accumulates the weighted sums into the bins, but does not finalize
        the calculation by dividing by the total weight at the end.  After
        calling this function as often as desired, the `finalize` command will
        finish the calculation.

        Parameters:
            cat1 (Catalog):     The first catalog to process
            cat2 (Catalog):     The second catalog to process
            metric (str):       Which metric to use.  See `Metrics` for details.
                                (default: 'Euclidean'; this value can also be given in the
                                constructor in the config dict.)
            num_threads (int):  How many OpenMP threads to use during the calculation.
                                (default: use the number of cpu cores; this value can also be given
                                in the constructor in the config dict.)
        """
        if cat1.name == '' and cat2.name == '':
            self.logger.info('Starting process KK cross-correlations')
        else:
            self.logger.info('Starting process KK cross-correlations for cats %s, %s.',
                             cat1.name, cat2.name)

        self._set_metric(metric, cat1.coords, cat2.coords)

        self._set_num_threads(num_threads)

        min_size, max_size = self._get_minmax_size()

        f1 = cat1.getKField(min_size, max_size, self.split_method,
                            self.brute is True or self.brute == 1,
                            self.min_top, self.max_top, self.coords)
        f2 = cat2.getKField(min_size, max_size, self.split_method,
                            self.brute is True or self.brute == 2,
                            self.min_top, self.max_top, self.coords)

        self.logger.info('Starting %d jobs.',f1.nTopLevelNodes)
        treecorr._lib.ProcessCross2(self.corr, f1.data, f2.data, self.output_dots,
                                    f1._d, f2._d, self._coords, self._bintype, self._metric)


    def process_pairwise(self, cat1, cat2, metric=None, num_threads=None):
        """Process a single pair of catalogs, accumulating the cross-correlation, only using
        the corresponding pairs of objects in each catalog.

        This accumulates the weighted sums into the bins, but does not finalize
        the calculation by dividing by the total weight at the end.  After
        calling this function as often as desired, the `finalize` command will
        finish the calculation.

        Parameters:
            cat1 (Catalog):     The first catalog to process
            cat2 (Catalog):     The second catalog to process
            metric (str):       Which metric to use.  See `Metrics` for details.
                                (default: 'Euclidean'; this value can also be given in the
                                constructor in the config dict.)
            num_threads (int):  How many OpenMP threads to use during the calculation.
                                (default: use the number of cpu cores; this value can also be given
                                in the constructor in the config dict.)
        """
        if cat1.name == '' and cat2.name == '':
            self.logger.info('Starting process KK pairwise-correlations')
        else:
            self.logger.info('Starting process KK pairwise-correlations for cats %s, %s.',
                             cat1.name, cat2.name)

        self._set_metric(metric, cat1.coords, cat2.coords)

        self._set_num_threads(num_threads)

        f1 = cat1.getKSimpleField()
        f2 = cat2.getKSimpleField()

        treecorr._lib.ProcessPair(self.corr, f1.data, f2.data, self.output_dots,
                                  f1._d, f2._d, self._coords, self._bintype, self._metric)


    def finalize(self, vark1, vark2):
        """Finalize the calculation of the correlation function.

        The `process_auto` and `process_cross` commands accumulate values in each bin,
        so they can be called multiple times if appropriate.  Afterwards, this command
        finishes the calculation by dividing each column by the total weight.

        Parameters:
            vark1 (float):  The kappa variance for the first field.
            vark2 (float):  The kappa variance for the second field.
        """
        mask1 = self.weight != 0
        mask2 = self.weight == 0

        self.xi[mask1] /= self.weight[mask1]
        self.meanr[mask1] /= self.weight[mask1]
        self.meanlogr[mask1] /= self.weight[mask1]

        # Update the units of meanlogr
        self._apply_units(mask1)

        # Use meanlogr when available, but set to nominal when no pairs in bin.
        self.meanr[mask2] = self.rnom[mask2]
        self.meanlogr[mask2] = self.logr[mask2]

        self._var_num = vark1 * vark2
        self.cov = self.estimate_cov(self.var_method)
        self.varxi.ravel()[:] = self.cov.diagonal()


    def clear(self):
        """Clear the data vectors
        """
        self.xi.ravel().ravel()[:] = 0
        self.meanr.ravel()[:] = 0
        self.meanlogr.ravel()[:] = 0
        self.weight.ravel()[:] = 0
        self.npairs.ravel()[:] = 0
        self.results.clear()

    def __iadd__(self, other):
        """Add a second KKCorrelation's data to this one.

        Note: For this to make sense, both Correlation objects should have been using
        `process_auto` and/or `process_cross`, and they should not have had `finalize` called yet.
        Then, after adding them together, you should call `finalize` on the sum.
        """
        if not isinstance(other, KKCorrelation):
            raise TypeError("Can only add another KKCorrelation object")
        if not (self._nbins == other._nbins and
                self.min_sep == other.min_sep and
                self.max_sep == other.max_sep):
            raise ValueError("KKCorrelation to be added is not compatible with this one.")

        self._set_metric(other.metric, other.coords)
        self.xi.ravel()[:] += other.xi.ravel()[:]
        self.meanr.ravel()[:] += other.meanr.ravel()[:]
        self.meanlogr.ravel()[:] += other.meanlogr.ravel()[:]
        self.weight.ravel()[:] += other.weight.ravel()[:]
        self.npairs.ravel()[:] += other.npairs.ravel()[:]
        return self


    def process(self, cat1, cat2=None, metric=None, num_threads=None, comm=None, low_mem=None):
        """Compute the correlation function.

        If only 1 argument is given, then compute an auto-correlation function.
        If 2 arguments are given, then compute a cross-correlation function.

        Both arguments may be lists, in which case all items in the list are used
        for that element of the correlation.

        Parameters:
            cat1 (Catalog):     A catalog or list of catalogs for the first K field.
            cat2 (Catalog):     A catalog or list of catalogs for the second K field, if any.
                                (default: None)
            metric (str):       Which metric to use.  See `Metrics` for details.
                                (default: 'Euclidean'; this value can also be given in the
                                constructor in the config dict.)
            num_threads (int):  How many OpenMP threads to use during the calculation.
                                (default: use the number of cpu cores; this value can also be given
                                in the constructor in the config dict.)
            comm (mpi4py.Comm): If running MPI, an mpi4py Comm object to communicate between
                                processes.  If used, the rank=0 process will have the final
                                computation. This only works if using patches. (default: None)
            low_mem (bool):     Whether to sacrifice a little speed to try to reduce memory usage.
                                This only works if using patches. (default: False)
        """
        import math
        self.clear()

        if not isinstance(cat1,list):
            self.npatch1 = cat1._npatch
            cat1 = cat1.get_patches(low_mem=low_mem)
            if cat2 is None: self.npatch2 = self.npatch1
        if cat2 is not None and not isinstance(cat2,list):
            self.npatch2 = cat2._npatch
            cat2 = cat2.get_patches(low_mem=low_mem)

        if cat2 is None:
            vark1 = treecorr.calculateVarK(cat1)
            vark2 = vark1
            self.logger.info("vark = %f: sig_k = %f",vark1,math.sqrt(vark1))
            self._process_all_auto(cat1, metric, num_threads, comm, low_mem)
        else:
            vark1 = treecorr.calculateVarK(cat1)
            vark2 = treecorr.calculateVarK(cat2)
            self.logger.info("vark1 = %f: sig_k = %f",vark1,math.sqrt(vark1))
            self.logger.info("vark2 = %f: sig_k = %f",vark2,math.sqrt(vark2))
            self._process_all_cross(cat1, cat2, metric, num_threads, comm, low_mem)
        self.finalize(vark1,vark2)


    def write(self, file_name, file_type=None, precision=None):
        """Write the correlation function to the file, file_name.

        The output file will include the following columns:

        ==========      ========================================================
        Column          Description
        ==========      ========================================================
        r_nom           The nominal center of the bin in r
        meanr           The mean value <r> of pairs that fell into each bin
        meanlogr        The mean value <log(r)> of pairs that fell into each bin
        xi              The estimate of the correlation function xi(r)
        sigma_xi        The sqrt of the variance estimate of xi(r)
        weight          The total weight contributing to each bin
        npairs          The total number of pairs in each bin
        ==========      ========================================================

        If **sep_units** was given at construction, then the distances will all be in these units.
        Otherwise, they will be in either the same units as x,y,z (for flat or 3d coordinates) or
        radians (for spherical coordinates).

        Parameters:
            file_name (str):    The name of the file to write to.
            file_type (str):    The type of file to write ('ASCII' or 'FITS').  (default: determine
                                the type automatically from the extension of file_name.)
            precision (int):    For ASCII output catalogs, the desired precision. (default: 4;
                                this value can also be given in the constructor in the config dict.)
        """
        self.logger.info('Writing KK correlations to %s',file_name)
        if precision is None:
            precision = self.config.get('precision', 4)

        params = { 'coords' : self.coords, 'metric' : self.metric,
                   'sep_units' : self.sep_units, 'bin_type' : self.bin_type }

        treecorr.util.gen_write(
            file_name,
            ['r_nom','meanr','meanlogr','xi','sigma_xi','weight','npairs'],
            [ self.rnom, self.meanr, self.meanlogr,
              self.xi, np.sqrt(self.varxi), self.weight, self.npairs ],
            params=params, precision=precision, file_type=file_type, logger=self.logger)


    def read(self, file_name, file_type=None):
        """Read in values from a file.

        This should be a file that was written by TreeCorr, preferably a FITS file, so there
        is no loss of information.

        Warning: The KKCorrelation object should be constructed with the same configuration
        parameters as the one being read.  e.g. the same min_sep, max_sep, etc.  This is not
        checked by the read function.

        Parameters:
            file_name (str):    The name of the file to read in.
            file_type (str):    The type of file ('ASCII' or 'FITS').  (default: determine the type
                                automatically from the extension of file_name.)
        """
        self.logger.info('Reading KK correlations from %s',file_name)

        data, params = treecorr.util.gen_read(file_name, file_type=file_type, logger=self.logger)
        if 'R_nom' in data.dtype.names:  # pragma: no cover
            self.rnom = data['R_nom']
            self.meanr = data['meanR']
            self.meanlogr = data['meanlogR']
        else:
            self.rnom = data['r_nom']
            self.meanr = data['meanr']
            self.meanlogr = data['meanlogr']
        self.logr = np.log(self.rnom)
        self.xi = data['xi']
        self.varxi = data['sigma_xi']**2
        self.weight = data['weight']
        self.npairs = data['npairs']
        self.coords = params['coords'].strip()
        self.metric = params['metric'].strip()
        self.sep_units = params['sep_units'].strip()
        self.bin_type = params['bin_type'].strip()
