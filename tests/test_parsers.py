"""Unit tests for the tolerant eSCL XML parsers. Pure — no HomeAssistant."""
import pytest

from custom_components.escl_scan.scanner import (
    parse_job_info,
    parse_scanner_status,
)


def test_status_hp_adf_loaded():
    xml = b"""<?xml version="1.0"?>
    <scan:ScannerStatus xmlns:scan="s" xmlns:pwg="p">
      <pwg:Version>2.63</pwg:Version>
      <pwg:State>Idle</pwg:State>
      <scan:AdfState>ScannerAdfLoaded</scan:AdfState>
    </scan:ScannerStatus>"""
    st = parse_scanner_status(xml)
    assert st.state == "Idle"
    assert st.adf_loaded is True
    assert st.is_idle is True


def test_status_no_adf_element():
    xml = b'<ScannerStatus><State>Processing</State></ScannerStatus>'
    st = parse_scanner_status(xml)
    assert st.state == "Processing"
    assert st.adf_loaded is False
    assert st.is_idle is False


def test_status_adf_empty_means_not_loaded():
    xml = (
        b'<ScannerStatus><State>Idle</State>'
        b'<AdfState>ScannerAdfEmpty</AdfState></ScannerStatus>'
    )
    assert parse_scanner_status(xml).adf_loaded is False


def test_status_missing_state_defaults_unknown():
    st = parse_scanner_status(b"<ScannerStatus></ScannerStatus>")
    assert st.state == "Unknown"


def test_status_job_uris_extracted():
    xml = (
        b'<ScannerStatus><State>Processing</State><Jobs>'
        b'<JobInfo><scan:JobUri xmlns:scan="s">/eSCL/ScanJobs/aaa</scan:JobUri></JobInfo>'
        b'<JobInfo><JobUri>/eSCL/ScanJobs/bbb</JobUri></JobInfo>'
        b'</Jobs></ScannerStatus>'
    )
    st = parse_scanner_status(xml)
    assert st.active_job_uris == ["/eSCL/ScanJobs/aaa", "/eSCL/ScanJobs/bbb"]


def test_status_invalid_xml_raises():
    with pytest.raises(ValueError):
        parse_scanner_status(b"<not xml")


def test_jobinfo_reasons_as_leaf():
    xml = (
        b'<ScanJob><JobState>Completed</JobState>'
        b'<JobStateReasons>JobCompletedSuccessfully</JobStateReasons>'
        b'<ImagesCompleted>3</ImagesCompleted></ScanJob>'
    )
    info = parse_job_info(xml)
    assert info.state == "Completed"
    assert info.state_reasons == "JobCompletedSuccessfully"
    assert info.pages_completed == 3
    assert info.is_terminal is True


def test_jobinfo_reasons_as_wrapper_with_child():
    xml = (
        b'<ScanJob><JobState>Processing</JobState>'
        b'<JobStateReasons><JobStateReason>JobScanning</JobStateReason></JobStateReasons>'
        b'</ScanJob>'
    )
    info = parse_job_info(xml)
    assert info.state == "Processing"
    assert info.state_reasons == "JobScanning"
    assert info.is_terminal is False


def test_jobinfo_pages_completed_fallback_name():
    xml = (
        b'<ScanJob><JobState>Processing</JobState>'
        b'<PagesCompleted>2</PagesCompleted></ScanJob>'
    )
    assert parse_job_info(xml).pages_completed == 2


def test_jobinfo_bad_pages_ignored():
    xml = (
        b'<ScanJob><JobState>Processing</JobState>'
        b'<ImagesCompleted>notanumber</ImagesCompleted></ScanJob>'
    )
    assert parse_job_info(xml).pages_completed is None


def test_jobinfo_missing_state_defaults_unknown():
    info = parse_job_info(b"<ScanJob></ScanJob>")
    assert info.state == "Unknown"
    assert info.is_terminal is False


def test_jobinfo_invalid_xml_raises():
    with pytest.raises(ValueError):
        parse_job_info(b"<broken")
