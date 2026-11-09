def check(ok, message):
    if not ok:
        raise ValueError(message)

def validate_video_probe(probe, minimum_duration):
    streams=probe.get('streams',[])
    check(len(streams)==1,'Require one video stream and no audio/extra streams')
    video=streams[0]
    check(video.get('codec_type')=='video' and video.get('codec_name')=='h264' and
          (video.get('width'),video.get('height'))==(1280,720),'Encoded video profile changed')
    rate=video.get('avg_frame_rate','').split('/')
    check(len(rate)==2 and all(x.isdigit() for x in rate) and int(rate[1])>0,'Missing encoded frame rate')
    fps=int(rate[0])/int(rate[1]);duration=float(probe.get('format',{}).get('duration','0'))
    check(29<=fps<=31 and minimum_duration<=duration<600,'Encoded duration/frame rate unqualified')
    return {'codec':'h264','size':[1280,720],'audio_streams':0,'encoded_average_fps':fps,
            'duration_seconds':duration,'pwm_hz':None}
