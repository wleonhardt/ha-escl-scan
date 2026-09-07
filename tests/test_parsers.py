"""Unit tests for the tolerant eSCL XML parsers. Pure — no HomeAssistant."""
import pytest

from custom_components.escl_scan.scanner import (
    DEFAULT_REGION,
    ScannerCapabilities,
    parse_job_info,
    parse_scanner_capabilities,
    parse_scanner_status,
)

CAPS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerCapabilities xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
                          xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
  <pwg:Version>2.63</pwg:Version>
  <pwg:MakeAndModel>HP LaserJet MFP M234sdw</pwg:MakeAndModel>
  <pwg:SerialNumber>CNB1234567</pwg:SerialNumber>
  <scan:UUID>3f9a-uuid</scan:UUID>
  <scan:Platen>
    <scan:PlatenInputCaps>
      <scan:MinWidth>8</scan:MinWidth><scan:MaxWidth>2550</scan:MaxWidth>
      <scan:MinHeight>8</scan:MinHeight><scan:MaxHeight>3508</scan:MaxHeight>
      <scan:SettingProfiles><scan:SettingProfile>
        <scan:ColorModes>
          <scan:ColorMode>Grayscale8</scan:ColorMode>
          <scan:ColorMode>RGB24</scan:ColorMode>
        </scan:ColorModes>
        <scan:SupportedResolutions><scan:DiscreteResolutions>
          <scan:DiscreteResolution><scan:XResolution>75</scan:XResolution><scan:YResolution>75</scan:YResolution></scan:DiscreteResolution>
          <scan:DiscreteResolution><scan:XResolution>300</scan:XResolution><scan:YResolution>300</scan:YResolution></scan:DiscreteResolution>
          <scan:DiscreteResolution><scan:XResolution>600</scan:XResolution><scan:YResolution>600</scan:YResolution></scan:DiscreteResolution>
        </scan:DiscreteResolutions></scan:SupportedResolutions>
      </scan:SettingProfile></scan:SettingProfiles>
    </scan:PlatenInputCaps>
  </scan:Platen>
  <scan:Adf>
    <scan:AdfSimplexInputCaps>
      <scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>4200</scan:MaxHeight>
    </scan:AdfSimplexInputCaps>
    <scan:AdfOptions><scan:AdfOption>DetectPaperLoaded</scan:AdfOption><scan:AdfOption>Duplex</scan:AdfOption></scan:AdfOptions>
  </scan:Adf>
</scan:ScannerCapabilities>"""


def test_capabilities_full_parse():
    caps = parse_scanner_capabilities(CAPS_XML)
    assert caps.make_and_model == "HP LaserJet MFP M234sdw"
    assert caps.serial_number == "CNB1234567"
    assert caps.device_id == "CNB1234567"
    assert caps.platen_max == (2550, 3508)
    assert caps.adf_max == (2550, 4200)
    assert caps.adf_duplex is True
    assert caps.resolutions == [75, 300, 600]
    assert caps.color_modes == ["Grayscale8", "RGB24"]
    assert caps.region_for("Platen") == (2550, 3508)
    assert caps.region_for("Feeder") == (2550, 4200)


def test_capabilities_snap_dpi_to_supported():
    caps = parse_scanner_capabilities(CAPS_XML)
    assert caps.snap_dpi(300) == 300
    assert caps.snap_dpi(200) == 300
    assert caps.snap_dpi(1200) == 600
    assert caps.snap_dpi(100) == 75
    assert ScannerCapabilities().snap_dpi(1200) == 1200  # unknown -> passthrough


def test_capabilities_minimal_document():
    caps = parse_scanner_capabilities(b"<ScannerCapabilities></ScannerCapabilities>")
    assert caps.device_id is None
    assert caps.region_for("Platen") == DEFAULT_REGION
    assert caps.adf_duplex is False
    assert caps.resolutions == []


def test_capabilities_uuid_fallback_and_duplex_caps_element():
    xml = (
        b'<ScannerCapabilities><UUID>u-1</UUID>'
        b'<Adf><AdfDuplexInputCaps><MaxWidth>2550</MaxWidth><MaxHeight>3508</MaxHeight>'
        b'</AdfDuplexInputCaps></Adf></ScannerCapabilities>'
    )
    caps = parse_scanner_capabilities(xml)
    assert caps.device_id == "u-1"
    assert caps.adf_duplex is True
    assert caps.adf_max == (2550, 3508)


def test_capabilities_invalid_xml_raises():
    with pytest.raises(ValueError):
        parse_scanner_capabilities(b"<nope")


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


HP_STATUS_XML = b"""<scan:ScannerStatus xmlns:scan="s" xmlns:pwg="p">
<pwg:Version>2.63</pwg:Version><pwg:State>Processing</pwg:State>
<scan:AdfState>ScannerAdfEmpty</scan:AdfState><scan:Jobs>
<scan:JobInfo><pwg:JobUri>/eSCL/ScanJobs/yk1l-1002</pwg:JobUri><pwg:JobUuid>yk1l-1002</pwg:JobUuid>
<scan:Age>7</scan:Age><pwg:ImagesCompleted>1</pwg:ImagesCompleted><pwg:ImagesToTransfer>1</pwg:ImagesToTransfer>
<pwg:JobState>Processing</pwg:JobState><pwg:JobStateReasons><pwg:JobStateReason>JobScanning</pwg:JobStateReason></pwg:JobStateReasons></scan:JobInfo>
<scan:JobInfo><pwg:JobUri>/eSCL/ScanJobs/yk1l-1001</pwg:JobUri><pwg:JobUuid>yk1l-1001</pwg:JobUuid>
<scan:Age>31</scan:Age><pwg:ImagesCompleted>3</pwg:ImagesCompleted><pwg:ImagesToTransfer>0</pwg:ImagesToTransfer>
<pwg:JobState>Completed</pwg:JobState><pwg:JobStateReasons><pwg:JobStateReason>JobCompletedSuccessfully</pwg:JobStateReason></pwg:JobStateReasons></scan:JobInfo>
</scan:Jobs></scan:ScannerStatus>"""


def test_status_jobs_parsed_from_hp_status():
    # Real HP M283fdw shape: GET ScanJobs/{uuid} is 404; state lives here.
    st = parse_scanner_status(HP_STATUS_XML)
    assert st.state == "Processing"
    assert list(st.jobs) == ["/eSCL/ScanJobs/yk1l-1002", "/eSCL/ScanJobs/yk1l-1001"]
    live = st.job("http://10.0.0.5:80/eSCL/ScanJobs/yk1l-1002")
    assert live.state == "Processing" and live.pages_completed == 1
    assert live.state_reasons == "JobScanning" and not live.is_terminal
    done = st.job("/eSCL/ScanJobs/yk1l-1001")
    assert done.is_terminal and done.pages_completed == 3
    assert st.job("/eSCL/ScanJobs/nope") is None


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
