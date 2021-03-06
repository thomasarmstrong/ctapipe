import numpy as np
import pytest
import copy
from ctapipe.utils import get_dataset_path
from ctapipe.io.simteleventsource import SimTelEventSource
from ctapipe.io.hessioeventsource import HESSIOEventSource
from itertools import zip_longest

gamma_test_large_path = get_dataset_path("gamma_test_large.simtel.gz")
gamma_test_path = get_dataset_path("gamma_test.simtel.gz")


def compare_sources(input_url):
    pytest.importorskip('pyhessio')

    with SimTelEventSource(input_url=input_url) as simtel_source, \
            HESSIOEventSource(input_url=input_url) as hessio_source:

        for s, h in zip_longest(simtel_source, hessio_source):

            assert s is not None
            assert h is not None

            assert h.count == s.count
            assert h.r0.obs_id == s.r0.obs_id
            assert h.r0.event_id == s.r0.event_id
            assert h.r0.tels_with_data == s.r0.tels_with_data

            assert (h.trig.tels_with_trigger == s.trig.tels_with_trigger).all()
            assert h.trig.gps_time == s.trig.gps_time

            assert h.mc.energy == s.mc.energy
            assert h.mc.alt == s.mc.alt
            assert h.mc.az == s.mc.az
            assert h.mc.core_x == s.mc.core_x
            assert h.mc.core_y == s.mc.core_y

            assert h.mc.h_first_int == s.mc.h_first_int
            assert h.mc.x_max == s.mc.x_max
            assert h.mc.shower_primary_id == s.mc.shower_primary_id
            assert (h.mcheader.run_array_direction == s.mcheader.run_array_direction).all()

            tels_with_data = s.r0.tels_with_data
            for tel_id in tels_with_data:

                assert h.mc.tel[tel_id].reference_pulse_shape.dtype == s.mc.tel[tel_id].reference_pulse_shape.dtype
                assert type(h.mc.tel[tel_id].meta['refstep']) is type(s.mc.tel[tel_id].meta['refstep'])
                assert type(h.mc.tel[tel_id].time_slice) is type(s.mc.tel[tel_id].time_slice)

                assert (h.mc.tel[tel_id].dc_to_pe == s.mc.tel[tel_id].dc_to_pe).all()
                assert (h.mc.tel[tel_id].pedestal == s.mc.tel[tel_id].pedestal).all()
                assert h.r0.tel[tel_id].waveform.shape == s.r0.tel[tel_id].waveform.shape
                assert np.allclose(h.r0.tel[tel_id].waveform, s.r0.tel[tel_id].waveform)
                assert (h.r0.tel[tel_id].num_samples == s.r0.tel[tel_id].num_samples)
                assert (h.r0.tel[tel_id].image == s.r0.tel[tel_id].image).all()

                assert h.r0.tel[tel_id].num_trig_pix == s.r0.tel[tel_id].num_trig_pix
                assert (h.r0.tel[tel_id].trig_pix_id == s.r0.tel[tel_id].trig_pix_id).all()
                assert (h.mc.tel[tel_id].reference_pulse_shape == s.mc.tel[tel_id].reference_pulse_shape).all()

                assert (h.mc.tel[tel_id].photo_electron_image == s.mc.tel[tel_id].photo_electron_image).all()
                assert h.mc.tel[tel_id].meta == s.mc.tel[tel_id].meta
                assert h.mc.tel[tel_id].time_slice == s.mc.tel[tel_id].time_slice
                assert h.mc.tel[tel_id].azimuth_raw == s.mc.tel[tel_id].azimuth_raw
                assert h.mc.tel[tel_id].altitude_raw == s.mc.tel[tel_id].altitude_raw


def test_compare_event_hessio_and_simtel():
    for input_url in (gamma_test_path, gamma_test_large_path):
        compare_sources(input_url)


def test_simtel_event_source_on_gamma_test_one_event():
    with SimTelEventSource(input_url=gamma_test_path) as reader:
        assert reader.is_compatible(gamma_test_path)
        assert not reader.is_stream

        for event in reader:
            if event.count == 0:
                assert event.r0.tels_with_data == {38, 47}
            elif event.count == 1:
                assert event.r0.tels_with_data == {11, 21, 24, 26, 61, 63, 118,
                                                   119}
            else:
                break
        for event in reader:
            # Check generator has restarted from beginning
            assert event.count == 0
            break

    # test that max_events works:
    max_events = 5
    with SimTelEventSource(input_url=gamma_test_path, max_events=max_events) as reader:
        count = 0
        for _ in reader:
            count += 1
        assert count == max_events

    # test that the allowed_tels mask works:
    with pytest.warns(UserWarning):
        with SimTelEventSource(
            input_url=gamma_test_path,
            allowed_tels={3, 4}
        ) as reader:
            for event in reader:
                assert event.r0.tels_with_data.issubset(reader.allowed_tels)


def test_that_event_is_not_modified_after_loop():

    dataset = gamma_test_path
    with SimTelEventSource(input_url=dataset, max_events=2) as source:
        for event in source:
            last_event = copy.deepcopy(event)

        # now `event` should be identical with the deepcopy of itself from
        # inside the loop.
        # Unfortunately this does not work:
        #      assert last_event == event
        # So for the moment we just compare event ids
        assert event.r0.event_id == last_event.r0.event_id


def test_additional_meta_data_from_mc_header():
    with SimTelEventSource(input_url=gamma_test_path) as reader:
        data = next(iter(reader))

    # for expectation values
    from astropy import units as u
    from astropy.coordinates import Angle

    assert data.mcheader.corsika_version == 6990
    assert data.mcheader.simtel_version == 1404919891
    assert data.mcheader.spectral_index == -2.0
    assert data.mcheader.shower_prog_start == 1408536000
    assert data.mcheader.shower_reuse == 10
    assert data.mcheader.core_pos_mode == 1
    assert data.mcheader.diffuse == 0
    assert data.mcheader.atmosphere == 24

    name_expectation = {
        'energy_range_min': u.Quantity(3.0e-03, u.TeV),
        'energy_range_max': u.Quantity(3.3e+02, u.TeV),
        'prod_site_B_total': u.Quantity(27.181243896484375, u.uT),
        'prod_site_B_declination': Angle(0.0 * u.rad),
        'prod_site_B_inclination': Angle(-1.1581752300262451 * u.rad),
        'prod_site_alt': 1640.0 * u.m,
        'max_scatter_range': 2500.0 * u.m,
        'min_az': 0.0 * u.rad,
        'min_alt': 1.2217305 * u.rad,
        'max_viewcone_radius': 0.0 * u.deg,
        'corsika_wlen_min': 250 * u.nm,

    }

    for name, expectation in name_expectation.items():
        value = getattr(data.mcheader, name)

        assert value.unit == expectation.unit
        assert np.isclose(
            value.to_value(expectation.unit),
            expectation.to_value(expectation.unit)
        )
