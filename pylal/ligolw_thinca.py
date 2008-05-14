# $Id$
#
# Copyright (C) 2008  Kipp C. Cannon
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


#
# =============================================================================
#
#                                   Preamble
#
# =============================================================================
#


import bisect
import math
import sys


from glue import iterutils
from glue.ligolw import table
from glue.ligolw import lsctables
from pylal import llwapp
from pylal import snglcoinc
from pylal.date import LIGOTimeGPS
from pylal import tools
from pylal.xlal import tools as xlaltools


__author__ = "Kipp Cannon <kipp@gravity.phys.uwm.edu>"
__version__ = "$Revision$"[11:-2]
__date__ = "$Date$"[7:-2]


#
# =============================================================================
#
#                                 Speed Hacks
#
# =============================================================================
#


lsctables.CoincMapTable.RowType = lsctables.CoincMap = xlaltools.CoincMap
lsctables.LIGOTimeGPS = LIGOTimeGPS


def sngl_inspiral___cmp__(self, other):
	# compare self's end time to the LIGOTimeGPS instance other
	return cmp(self.end_time, other.seconds) or cmp(self.end_time_ns, other.nanoseconds)

lsctables.SnglInspiral.__cmp__ = sngl_inspiral___cmp__


def use___segments(modulename):
	from glue import __segments
	modulename.segments.infinity = __segments.infinity
	modulename.segments.NegInfinity = __segments.NegInfinity
	modulename.segments.PosInfinity = __segments.PosInfinity
	modulename.segments.segment = __segments.segment
	modulename.segments.segmentlist = __segments.segmentlist
use___segments(llwapp)
use___segments(lsctables)


#
# =============================================================================
#
#                           Add Process Information
#
# =============================================================================
#


process_program_name = "ligolw_thinca"


def append_process(xmldoc, comment = None, force = None, program = None, e_thinca_parameter = None, verbose = None):
	process = llwapp.append_process(xmldoc, program = process_program_name, version = __version__, cvs_repository = "lscsoft", cvs_entry_time = __date__, comment = comment)

	params = [
		("--program", "lstring", program),
		("--e-thinca-parameter", "real_8", e_thinca_parameter)
	]
	if comment is not None:
		params += [("--comment", "lstring", comment)]
	if force is not None:
		params += [("--force", None, None)]
	if verbose is not None:
		params += [("--verbose", None, None)]

	llwapp.append_process_params(xmldoc, process, params)

	return process


#
# =============================================================================
#
#                          CoincTables Customizations
#
# =============================================================================
#


InspiralCoincDef = lsctables.CoincDef(search = u"inspiral", search_coinc_type = 0, description = u"sngl_inspiral<-->sngl_inspiral coincidences")


class InspiralCoincTables(snglcoinc.CoincTables):
	pass


#
# =============================================================================
#
#                            Event List Management
#
# =============================================================================
#


class InspiralEventList(snglcoinc.EventList):
	"""
	A customization of the EventList class for use with the inspiral
	search.
	"""
	def make_index(self):
		"""
		Sort events by end time so that a bisection search can
		retrieve them.  Note that the bisection search relies on
		the __cmp__() method of the SnglInspiral row class having
		previously been set to compare the event's peak time to a
		LIGOTimeGPS.
		"""
		# sort by end time
		self.sort(lambda a, b: cmp(a.end_time, b.end_time) or cmp(a.end_time_ns, b.end_time_ns))

	def _add_offset(self, delta):
		"""
		Add an amount to the end time of each event.
		"""
		for event in self:
			event.set_end(event.get_end() + delta)

	def get_coincs(self, event_a, e_thinca_parameter, comparefunc):
		# event_a's end time
		end = event_a.get_end()

		# if event_a's end time differs by more than this much from
		# the end time of an event in this list then it is
		# *impossible* for them to be coincident
		# FIXME:  use getTimeError() function in LAL to compute
		# this (current that's a static function, so it'll have to
		# be renamed and exported as part of the LAL API).
		dt = 0.5

		# extract the subset of events from this list that pass
		# coincidence with event_a (use bisection searches for the
		# minimum and maximum allowed end times to quickly identify
		# a subset of the full list)
		return [event_b for event_b in self[bisect.bisect_left(self, end - dt) : bisect.bisect_right(self, end + dt)] if not comparefunc(event_a, event_b, e_thinca_parameter)]


#
# =============================================================================
#
#                              Coincidence Tests
#
# =============================================================================
#


def inspiral_coinc_compare(a, b, e_thinca_parameter):
	"""
	Returns False (a & b are coincident) if they pass the ellipsoidal
	thinca test.
	"""
	try:
		# FIXME:  should it be ">" or ">="?
		return tools.XLALCalculateEThincaParameter(a, b) > e_thinca_parameter
	except ValueError:
		# ethinca test failed to converge == events are not
		# coincident
		return True


#
# =============================================================================
#
#                                 Library API
#
# =============================================================================
#


def replicate_threshold(e_thinca_parameter, instruments):
	"""
	From a single threshold and a list of instruments, return a
	dictionary whose keys are every instrument pair (both orders), and
	whose values are all the same single threshold.

	Example:

	>>> replicate_threshold(6, ["H1", "H2"])
	{("H1", "H2"): 6, ("H2", "H1"): 6}
	"""
	instruments = list(instruments)
	instruments.sort()
	thresholds = dict([(pair, e_thinca_parameter) for pair in list(iterutils.choices(instruments, 2))])
	instruments.reverse()
	thresholds.update(dict([(pair, e_thinca_parameter) for pair in list(iterutils.choices(instruments, 2))]))
	return thresholds


def ligolw_thinca(
	xmldoc,
	program,
	process_id,
	EventListType,
	CoincTables,
	coinc_definer_row,
	event_comparefunc,
	thresholds,
	ntuple_comparefunc = lambda events: False,
	get_max_segment_gap = lambda xmldoc, thresholds: float("inf"),
	verbose = False
):
	#
	# prepare the coincidence table interface
	#

	if verbose:
		print >>sys.stderr, "indexing ..."
	coinc_tables = CoincTables(xmldoc, coinc_definer_row)

	#
	# build the event list accessors, populated with events from those
	# processes that can participate in a coincidence
	#

	eventlists = snglcoinc.make_eventlists(xmldoc, EventListType, lsctables.SnglInspiralTable.tableName, get_max_segment_gap(xmldoc, thresholds), program)
	avail_instruments = set(eventlists.keys())

	#
	# replicate the ethinca parameter for every possible instrument
	# pair
	#

	thresholds = replicate_threshold(thresholds, avail_instruments)

	#
	# iterate over time slides
	#

	time_slide_ids = coinc_tables.time_slide_ids()
	for n, time_slide_id in enumerate(time_slide_ids):
		#
		# retrieve the current time slide
		#

		offsetdict = coinc_tables.get_time_slide(time_slide_id)
		offset_instruments = set(offsetdict.keys())
		if verbose:
			print >>sys.stderr, "time slide %d/%d: %s" % (n + 1, len(time_slide_ids), ", ".join(["%s = %+.16g s" % (i, o) for i, o in offsetdict.items()]))

		#
		# can we do it?
		#

		if len(offset_instruments) < 2:
			if verbose:
				print >>sys.stderr, "\tsingle-instrument time slide: skipped"
			continue
		if not offset_instruments.issubset(avail_instruments):
			if verbose:
				print >>sys.stderr, "\twarning: do not have data for instrument(s) %s: skipping" % ", ".join(offset_instruments - avail_instruments)
			continue

		#
		# apply offsets to events
		#

		if verbose:
			print >>sys.stderr, "\tapplying time offsets ..."
		eventlists.set_offsetdict(offsetdict)

		#
		# search for and record coincidences
		#

		if verbose:
			print >>sys.stderr, "\tsearching ..."
		for ntuple in snglcoinc.CoincidentNTuples(eventlists, event_comparefunc, offset_instruments, thresholds, verbose = verbose):
			if not ntuple_comparefunc(ntuple):
				coinc_tables.append_coinc(process_id, time_slide_id, ntuple)

	#
	# remove time offsets from events
	#

	eventlists.remove_offsetdict()

	#
	# done
	#

	return xmldoc