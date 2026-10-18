#!/usr/bin/env python3
"""Verify local ASR using synthetic Polish speech, never a user's live microphone."""
import argparse
import ctypes
import ctypes.util
import json
import re
import wave
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]


def synthesize(text, path):
    library=ctypes.util.find_library('espeak-ng')
    if not library:
        raise RuntimeError('Test wymaga biblioteki libespeak-ng1 lub własnego pliku --audio.')
    espeak=ctypes.CDLL(library)
    chunks=[]
    callback_type=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.POINTER(ctypes.c_short),ctypes.c_int,ctypes.c_void_p)
    @callback_type
    def callback(samples,count,events):
        if samples and count:
            chunks.append(ctypes.string_at(samples,count*2))
        return 0
    espeak.espeak_Initialize.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_char_p,ctypes.c_int]
    rate=espeak.espeak_Initialize(2,0,None,0)  # synchronous retrieval, no speaker playback
    if rate<=0:
        raise RuntimeError('Nie można uruchomić syntezy testowej.')
    espeak.espeak_SetSynthCallback(callback)
    espeak.espeak_SetVoiceByName(b'pl')
    espeak.espeak_SetParameter(1,145,0)
    data=text.encode('utf-8')
    espeak.espeak_Synth.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_uint,ctypes.c_int,
                                 ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
    result=espeak.espeak_Synth(data,len(data)+1,0,1,0,1,None,None)
    espeak.espeak_Synchronize()
    espeak.espeak_Terminate()
    if result:
        raise RuntimeError('Synteza testowa nie powiodła się.')
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(rate)
        wav.writeframes(b''.join(chunks))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio',type=Path)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    out=ROOT/'artifacts/speech-check';out.mkdir(parents=True,exist_ok=True)
    audio=args.audio or out/'polish-command.wav'
    if not args.audio:
        synthesize('Jedź do sektora A i wróć do bazy.',audio)
    base=f'http://127.0.0.1:{args.port}'
    def api(path):
        with urlopen(base+path,timeout=5) as response:
            return json.load(response)
    before=api('/api/status')
    before_history=api('/api/history?limit=1')
    request=Request(base+'/api/speech/transcribe',data=audio.read_bytes(),headers={'Content-Type':'audio/wav'})
    with urlopen(request,timeout=120) as response:
        transcript=json.load(response)
    if not args.audio:
        assert re.search(r'\bA\b',transcript['text'],re.I), transcript
        assert 'baz' in transcript['text'].lower(),transcript
    after=api('/api/status')
    assert after.get('mission_id')==before.get('mission_id')
    assert api('/api/history?limit=1')==before_history
    assert not after['busy']
    result={'passed':True,'source':'synthetic_polish' if not args.audio else 'supplied_audio',
            'transcript':transcript,'mission_created':False,'microphone_hardware_tested':False}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
