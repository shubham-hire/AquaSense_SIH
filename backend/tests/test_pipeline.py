from app.pipeline import inspect_file, run_pipeline


def test_pipeline_never_fabricates_coordinates_for_image_upload(tmp_path):
    # A minimal valid PNG header/image is more reliable than a vendor sonar fixture.
    from PIL import Image
    source = tmp_path / "survey.png"
    Image.new("L", (16, 16), color=80).save(source)
    qc, extraction = inspect_file("survey-1", source, "survey.png")
    result = run_pipeline("survey-1", source, qc.model_dump(), dsp_applied=False)
    assert result
    assert result[0]["position"]["latitude"] is None
    assert result[0]["position"]["longitude"] is None
    assert result[0]["position"]["position_source"] == "UNAVAILABLE"
    assert result[0]["calibrated"] is False


def test_xtf_extraction_reads_samples_and_per_ping_navigation(tmp_path):
    import ctypes
    from datetime import datetime
    import numpy as np
    import pyxtf

    source = tmp_path / "fixture.xtf"
    header = pyxtf.XTFFileHeader()
    header.SonarName = b"AquaSense test"
    header.SonarType = pyxtf.XTFSonarType.unknown1
    header.NavUnits = pyxtf.XTFNavUnits.latlon.value
    header.NumberOfSonarChannels = 2
    for channel, kind in enumerate((pyxtf.XTFChannelType.port, pyxtf.XTFChannelType.stbd)):
        header.ChanInfo[channel].TypeOfChannel = kind.value
        header.ChanInfo[channel].SubChannelNumber = channel
        header.ChanInfo[channel].BytesPerSample = 1
        header.ChanInfo[channel].SampleFormat = pyxtf.XTFSampleFormat.byte.value

    now = datetime.now()
    pings = []
    for index in range(2):
        ping = pyxtf.XTFPingHeader()
        ping.HeaderType = pyxtf.XTFHeaderType.sonar.value
        ping.NumChansToFollow = 2
        ping.Year, ping.Month, ping.Day = now.year, now.month, now.day
        ping.Hour, ping.Minute, ping.Second = now.hour, now.minute, now.second
        ping.PingNumber = index
        ping.SoundVelocity = 1500
        ping.SensorYcoordinate, ping.SensorXcoordinate = 12.34 + index / 100, 76.78 + index / 100
        ping.SensorPrimaryAltitude, ping.SensorDepth, ping.SensorHeading = 8.0, 100.0, 45.0
        channels = (pyxtf.XTFPingChanHeader(), pyxtf.XTFPingChanHeader())
        for channel, entry in enumerate(channels):
            entry.ChannelNumber, entry.NumSamples, entry.SampleFormat = channel, 8, 8
            entry.SlantRange, entry.Frequency = 25, 410
        ping.ping_chan_headers = channels
        ping.data = [np.arange(8, dtype=np.uint8), np.arange(8, dtype=np.uint8)[::-1]]
        ping.NumBytesThisRecord = ctypes.sizeof(pyxtf.XTFPingHeader) + 2 * ctypes.sizeof(pyxtf.XTFPingChanHeader) + 16
        pings.append(ping)
    with source.open("wb") as output:
        output.write(header.to_bytes())
        for ping in pings:
            output.write(ping.to_bytes())

    qc, extraction = inspect_file("survey-xtf", source, source.name, tmp_path / "artifacts")
    assert qc.ping_count == 2
    assert extraction is not None
    assert extraction["waterfall_shape"] == [2, 16]
    assert extraction["valid_navigation_pings"] == 2
    assert extraction["navigation"][0]["latitude"] == 12.34
    assert (tmp_path / "artifacts" / "waterfall.png").is_file()
