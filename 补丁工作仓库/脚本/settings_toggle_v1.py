"""Four-row native settings menu, optional 10s grace; builds candidates only."""
import hashlib, json, struct
from pathlib import Path
import flash_v4 as pe

BASE = '79bee7aceeaff38953b242c3b9781ac717a79b3c'
ROOT = pe.ROOT
ASSETS=ROOT/'补丁工作仓库/候选版本/settings-toggle-v1/Resource'
PANEL_NAMES=[f'np_option_{state}_{row}.png' for state in ('off','on') for row in range(4)]
SIZE=0x2000

def imports(data):
    _, opt, _ = pe.pe_info(data)
    rva, size = struct.unpack_from('<II', data, opt+104)
    result = {}
    def string(r):
        return data[pe.rva_offset(data,r):].split(b'\0',1)[0].decode('ascii')
    for off in range(pe.rva_offset(data,rva), pe.rva_offset(data,rva)+size,20):
        oft, _, _, dll, ft = struct.unpack_from('<IIIII',data,off)
        if not dll: break
        i=0
        while True:
            n=struct.unpack_from('<I',data,pe.rva_offset(data,oft or ft)+4*i)[0]
            if not n: break
            if not n&0x80000000: result[string(n+2)]=pe.IMAGE_BASE+ft+4*i
            i+=1
    return result

def payload(origin, iat):
    a=pe.Asm(origin); sy={}; state=origin+0x1700; strings=origin+0x1800
    duration=state; loaded=state+4; buffer=state+8; widget_loaded=state+24
    ids=state+32; changed=state+64; activate=state+68; save_error=state+72; io_count=state+76
    textdata=bytearray(); text={}
    for name in ['newpal_patch.dat','rb','wb',*PANEL_NAMES]:
        text[name]=strings+len(textdata);textdata.extend(name.encode('ascii')+b'\0')
    def op(code,address,suffix=b''): a.raw(bytes.fromhex(code)+pe.u32(address)+suffix)
    def imm(v): a.raw(b'\x68'+pe.u32(v))
    def store(addr,v): op('c7 05',addr,pe.u32(v))
    def cmp(addr,v): op('81 3d',addr,pe.u32(v))
    def start(n): sy[n]=a.pc;a.label(n)
    def call(n): a.jump('e8',n)
    def regcall(address): a.raw(b'\xb9'+pe.u32(0x570b38));call(address)
    def rwopen(mode):
        imm(text['newpal_patch.dat']);a.raw(b'\xb9'+pe.u32(0x5352e0));call(0x458d40)
        # Use the game's own ANSI file wrapper, like env.dat. SDL_RWFromFile
        # expects UTF-8 and would break native paths containing non-ASCII names.
        imm(3 if mode=='rb' else 2);imm(0);imm(0);imm(0x80000000 if mode=='rb' else 0x40000000)
        a.raw('50');call(0x458f60);a.raw('83 c4 14 85 c0')

    start('load')
    a.raw('9c 60');cmp(loaded,0);a.jump('0f 85','load_done')
    # A first gate may run before initialization has populated the native user path.
    op('80 3d',0x536ae0,b'\x00');a.jump('0f 84','load_done')
    store(loaded,1);rwopen('rb');a.jump('0f 84','load_done');a.raw('8b f0')
    # Read at most nine bytes to reject truncated AND overlong files.
    store(io_count,0);imm(io_count);imm(9);imm(buffer);a.raw('56');call(0x459110);a.raw('83 c4 10')
    op('8b 3d',io_count);a.raw('56');call(0x458f40);a.raw('83 c4 04')
    a.raw('83 ff 08');a.jump('0f 85','load_done')
    cmp(buffer,int.from_bytes(b'NPO1','little'));a.jump('0f 85','load_done')
    op('a1',buffer+4);a.raw('85 c0');a.jump('0f 84','load_valid');a.raw('3d 10 27 00 00');a.jump('0f 85','load_done')
    a.label('load_valid');op('a3',duration)
    a.label('load_done');a.raw('61 9d c3')

    start('save')
    a.raw('9c 60');store(save_error,1);rwopen('wb');a.jump('0f 84','save_done');a.raw('8b f0')
    store(buffer,int.from_bytes(b'NPO1','little'));op('a1',duration);op('a3',buffer+4)
    store(io_count,0);imm(io_count);imm(8);imm(buffer);a.raw('56');call(0x459190);a.raw('83 c4 10')
    op('8b 3d',io_count);a.raw('56');call(0x458f40);a.raw('83 c4 04 84 c0')
    a.jump('0f 84','save_done');a.raw('83 ff 08');a.jump('0f 85','save_done');store(save_error,0)
    a.label('save_done');a.raw('61 9d c3')

    start('disabled')
    call('load');a.raw('31 c0');cmp(duration,0);a.jump('0f 84','disabled_true')
    cmp(0x56f338,4996);a.jump('0f 85','disabled_done')
    op('f6 05',0x56f7aa,b'\x01');a.jump('0f 84','disabled_done')
    cmp(0x56f334,0);a.jump('0f 8c','disabled_done')
    a.label('disabled_true');a.raw('b8 01 00 00 00')
    a.label('disabled_done');a.raw('c3')

    start('widgets')
    cmp(widget_loaded,0);a.jump('0f 85','widgets_done');store(widget_loaded,1)
    for i,n in enumerate(PANEL_NAMES):
        imm(1);imm(text[n]);imm(0);regcall(0x4af910);op('a3',ids+i*4)
    a.label('widgets_done');a.raw('c3')

    start('draw')
    a.raw('9c 60');call('load');call('widgets');op('a1',0x581494)
    cmp(0x531b50,9);a.jump('0f 85','draw_selection');a.raw('b8 03 00 00 00')
    a.label('draw_selection');a.raw('83 e0 03');cmp(duration,0);a.jump('0f 84','draw_off');a.raw('83 c0 04')
    a.label('draw_off');a.raw(b'\x8b\x04\x85'+pe.u32(ids))
    # Verify new widget is loaded; a missing pack must not dereference a bad slot.
    op('3b 05',0x570b3c);a.jump('0f 83','draw_fallback')
    op('8b 15',0x570b38);a.raw('8b 14 82 85 d2');a.jump('0f 84','draw_fallback')
    a.raw('80 3a 00');a.jump('0f 84','draw_fallback')
    a.raw('8b 52 04 85 d2');a.jump('0f 84','draw_fallback')
    a.raw('83 3a 00');a.jump('0f 84','draw_fallback')
    imm(50);imm(71);imm(0);a.raw('50');regcall(0x4afa10)
    for ptr,y in ((0x5814a4,115),(0x5814a8,147)):
        op('a1',ptr);a.raw('85 c0');a.jump('0f 84','draw_slider_'+str(y))
        a.raw('8b 00 d1 e8 05 99 00 00 00');imm(y);a.raw('50');imm(0);imm(0x4f);regcall(0x4afa10)
        a.label('draw_slider_'+str(y))
    a.jump('e9','draw_done')
    a.label('draw_fallback')
    # Original backgrounds cover only rows0..2. Keep fallback stable for row3.
    op('ff 35',0x581494);cmp(0x581494,3);a.jump('0f 82','fallback_call');store(0x581494,2)
    a.label('fallback_call');call(origin+0x1600);op('8f 05',0x581494)
    a.label('draw_done');a.raw('61 9d c3')

    # Set duration EAX; this helper preserves registers and writes only on change.
    start('set_duration')
    op('3b 05',duration);a.jump('0f 84','set_done');op('a3',duration);call('save');store(changed,1)
    a.label('set_done');a.raw('c3')

    # EAX requested volume, EBX row0/1. Native setters keep music/SFX behavior.
    start('volume')
    a.raw('85 c0');a.jump('0f 89','volume_min');a.raw('31 c0')
    a.label('volume_min');a.raw('83 f8 7f');a.jump('0f 8e','volume_max');a.raw('b8 7f 00 00 00')
    a.label('volume_max');a.raw('8b 14 9d a4 14 58 00 85 d2');a.jump('0f 84','volume_done')
    a.raw('39 02');a.jump('0f 84','volume_done');a.raw('89 02 50 85 db');a.jump('0f 85','volume_sfx')
    call(0x4c53f0);a.jump('e9','volume_return')
    a.label('volume_sfx');call(0x4c5410)
    a.label('volume_return');a.raw('83 c4 04');store(changed,1)
    a.label('volume_done');a.raw('c3')

    start('input')
    a.raw('9c 60');call('load');store(changed,0);store(activate,0)
    op('a1',0x581494);a.raw('83 e0 03');op('a3',0x581494)
    cmp(0x580c88,2);a.jump('0f 85','keys')
    # Half-open hit rectangles follow the supplied four-row PNG, not the old art.
    for addr,lo,hi in ((0x53b8c0,95,243),(0x53b8c4,110,242)):
        cmp(addr,lo);a.jump('0f 8c','confirm');cmp(addr,hi);a.jump('0f 8d','confirm')
    a.raw('31 db');op('a1',0x53b8c4)
    for threshold in (144,176,208):
        a.raw(b'\x3d'+pe.u32(threshold));a.jump('0f 8c','mouse_row');a.raw('43')
    a.label('mouse_row');op('3b 1d',0x581494);a.jump('0f 84','mouse_action');op('89 1d',0x581494);store(changed,1)
    a.label('mouse_action');a.raw('83 fb 02');a.jump('0f 83','mouse_choice')
    op('80 3d',0x580dc0,b'\x01');a.jump('0f 84','mouse_volume')
    op('80 3d',0x580dc0,b'\x02');a.jump('0f 85','confirm')
    op('c6 05',0x580dc0,b'\x00')
    a.label('mouse_volume');cmp(0x53b8c0,153);a.jump('0f 8c','confirm')
    op('a1',0x53b8c0);a.raw('2d a5 00 00 00 01 c0');call('volume');a.jump('e9','confirm')
    a.label('mouse_choice');op('80 3d',0x580dc0,b'\x02');a.jump('0f 85','confirm')
    op('c6 05',0x580dc0,b'\x00');store(activate,1);a.jump('e9','confirm')

    a.label('keys')
    for name,fn,delta in (('up',0x4e1e80,-1),('down',0x4e0c90,1)):
        call(fn);a.raw('85 c0');a.jump('0f 84',name+'_done')
        op('a1',0x581494);a.raw('48' if delta<0 else '40');a.raw('83 e0 03');op('a3',0x581494);store(changed,1)
        a.label(name+'_done')
    for name,fn,delta in (('left',0x4e1740,-13),('right',0x4e1bc0,13)):
        call(fn);a.raw('85 c0');a.jump('0f 84',name+'_done');op('8b 1d',0x581494)
        a.raw('83 fb 02');a.jump('0f 84',name+'_duration');a.jump('0f 87',name+'_done')
        a.raw('8b 14 9d a4 14 58 00 85 d2');a.jump('0f 84',name+'_done')
        a.raw('8b 02 05'+pe.u32(delta).hex());call('volume');a.jump('e9',name+'_done')
        a.label(name+'_duration');a.raw(b'\xb8'+pe.u32(0 if delta<0 else 10000));call('set_duration')
        a.label(name+'_done')

    a.label('confirm');call(0x4e0a90);a.raw('85 c0');a.jump('0f 85','activated')
    cmp(activate,0);a.jump('0f 84','input_finish')
    a.label('activated');op('a1',0x581494);a.raw('83 f8 02');a.jump('0f 84','toggle');a.raw('83 f8 03');a.jump('0f 85','input_finish')
    store(0x531b50,9);store(0x581494,0);store(0x581498,1);store(0x58149c,0);store(changed,1)
    call(0x4e0a40);a.jump('e9','input_finish')
    a.label('toggle');op('a1',duration);a.raw('35 10 27 00 00');call('set_duration');call(0x4e0a40)
    a.label('input_finish');cmp(changed,0);a.jump('0f 84','input_done')
    op('ff 35',0x5814c8);call(0x4f3280);a.raw('83 c4 04 c7 45 f0 01 00 00 00')
    a.label('input_done');a.raw('61 9d');a.jump('e9',0x4bb1b7)
    blob=a.finish();assert len(blob)<0x1600,hex(len(blob))
    blob+=bytes(0x1600-len(blob))
    # Original draw prologue displaced by entry jump.
    blob+=bytes.fromhex('55 8b ec 83 3d 94 14 58 00 03')+pe.branch(0xe9,origin+0x160a,0x4bb6da)
    blob+=bytes(0x1700-len(blob))+pe.u32(10000)
    blob+=bytes(0x1800-len(blob))+textdata
    blob+=bytes(SIZE-len(blob))
    return dict(blob=blob,origin=origin,symbols=sy,state=state,duration=duration,loaded=loaded,
                buffer=buffer,ids=ids,widget_loaded=widget_loaded,save_error=save_error,strings=text,code_size=len(a.buf))

def candidate(source=None):
    source=(ROOT/'NewPAL_Release.exe').read_bytes() if source is None else source
    if hashlib.sha1(source).hexdigest()!=BASE:raise ValueError('Expected v11 source')
    header,opt,sections=pe.pe_info(source);last=sections[-1]
    if last[0]!=b'.palhov' or last[1]!=0x2000 or last[3]!=0x2000 or last[4]+last[3]!=len(source):raise ValueError('Last section differs')
    origin=pe.IMAGE_BASE+last[2]+0x2000;plan=payload(origin,imports(source))
    out=bytearray(source);out.extend(plan['blob'])
    sh=opt+struct.unpack_from('<H',source,header+20)[0]+(len(sections)-1)*40
    struct.pack_into('<I',out,sh+8,0x4000);struct.pack_into('<I',out,sh+16,0x4000)
    struct.pack_into('<I',out,opt+56,last[2]+0x4000)
    struct.pack_into('<I',out,opt+4,struct.unpack_from('<I',source,opt+4)[0]+SIZE)
    struct.pack_into('<I',out,opt+64,0)
    rule=next(s for s in sections if s[0]==b'.palrule')
    patches={0xb9550:(bytes.fromhex('c6 45 e1 00 83 3d 88 0c 58 00 02'),pe.branch(0xe9,0x4b9550,plan['symbols']['input'])+bytes.fromhex('90 90 90 90 90 90')),
             0xbb6d0:(bytes.fromhex('55 8b ec 83 3d 94 14 58 00 03'),pe.branch(0xe9,0x4bb6d0,plan['symbols']['draw'])+b'\x90'*5),
             0xb8258:(pe.u32(2),pe.u32(3)),0xba703:(pe.u32(2),pe.u32(3)),
             rule[2]:(bytes.fromhex('31 c0 81 3d 38'),pe.branch(0xe9,pe.IMAGE_BASE+rule[2],plan['symbols']['disabled']))}
    for site,(expected,value) in patches.items():
        off=pe.rva_offset(source,site)
        if source[off:off+len(expected)]!=expected:raise ValueError('Unexpected site '+hex(site)+': '+source[off:off+len(expected)].hex())
        assert len(value)==len(expected);out[off:off+len(value)]=value
    plan['patches']=patches;plan['rules']=pe.IMAGE_BASE+rule[2]
    return bytes(out),plan

def main():
    out,plan=candidate();path=ROOT/'补丁工作仓库/候选版本/NewPAL_Release.settings-toggle-v1.exe';path.write_bytes(out)
    report={k:v for k,v in plan.items() if k not in ('blob','patches')}
    report.update(status='candidate; offline and gameplay validation pending',baseline_sha1=BASE,candidate_sha1=hashlib.sha1(out).hexdigest(),resources=PANEL_NAMES)
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
