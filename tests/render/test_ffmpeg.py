from nolane_studio.render.ffmpeg import (
    FFmpegPaths,
    build_concat_command,
    build_global_audio_mux_command,
    build_normalize_segment_command,
)


def test_normalize_segment_command_matches_recovered_h264_contract():
    cmd = build_normalize_segment_command(
        FFmpegPaths("ffmpeg", "ffprobe"), "base.mp4", "final.mp4", width=1280, height=720, fps=24
    )
    assert cmd[:4] == ["ffmpeg", "-y", "-i", "base.mp4"]
    assert "scale=1280:720:force_original_aspect_ratio=decrease" in cmd[cmd.index("-vf") + 1]
    assert "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=white" in cmd[cmd.index("-vf") + 1]
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd[-1] == "final.mp4"


def test_concat_command_uses_stream_copy_like_reference_export():
    cmd = build_concat_command(FFmpegPaths("ffmpeg", "ffprobe"), "segments.ffconcat", "joined.mp4")
    assert cmd == [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "segments.ffconcat",
        "-c", "copy", "-movflags", "+faststart", "joined.mp4"
    ]


def test_global_audio_mux_pads_and_trims_voice_to_video_duration():
    cmd = build_global_audio_mux_command(
        FFmpegPaths("ffmpeg", "ffprobe"), "joined.mp4", "voice.wav", "final.mp4", 12.5
    )
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "apad" in filt
    assert "atrim=0:12.500000" in filt
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert cmd[cmd.index("-c:a") + 1] == "aac"
