"""Direct native pixel export partitioned by a flag field, no image generation.

Field partitions are research views, never asserted to be ground/ceiling layers.
"""
import argparse,hashlib,json,shutil,sqlite3,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];WORK=ROOT/'补丁工作仓库';MAP=WORK/'地图开发'

def main():
 p=argparse.ArgumentParser();p.add_argument('--scene',type=int,required=True);p.add_argument('--mask',type=lambda s:int(s,0),default=0xf000);args=p.parse_args()
 db=sqlite3.connect((MAP/'地图索引/scene_export_index.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;scene=dict(db.execute('select * from scenes where scene_id=?',(args.scene,)).fetchone());db.close();rid=scene['map_resource_id'];source=WORK/scene['artwork_image'];before=source.read_bytes();im=Image.open(source).convert('RGBA');pixels=np.asarray(im);w,h=im.size;gw,gh=scene['grid_width'],scene['grid_height'];assert (w,h)==(gw*16,gh*16)
 with zipfile.ZipFile(MAP/'地图测试工具/原生格数据.zip') as z:raw=z.read(f'{rid}.bin')
 flags=np.frombuffer(raw,dtype='<u4').reshape(gh,gw);grouped=flags&args.mask;values=sorted(int(x) for x in np.unique(grouped));out=MAP/f'原生分组试导出/{args.scene}_罗刹洞' if args.scene==512 else MAP/f'原生分组试导出/{args.scene}'
 out.mkdir(parents=True,exist_ok=True);original=out/f'{args.scene}_完整原图.png'
 if original.exists():assert original.read_bytes()==before
 else:shutil.copy2(source,original)
 visible=np.any(pixels[:,:,:3]!=0,axis=2);coverage=np.zeros((h,w),dtype='u1');rows=[];preview=Image.new('RGB',(1536,76+440*((len(values)+2)//3)),'#eee9df');draw=ImageDraw.Draw(preview);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18);small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16);draw.text((16,10),f'场景{args.scene}：按0x{args.mask:X}字段直接分组（并非已确认的地面／前景层）',font=font,fill='#333333');draw.text((16,39),'所有PNG保留原尺寸和像素位置；仅将各组以外及纯黑像素设为透明。',font=small,fill='#555555')
 for i,value in enumerate(values):
  mask=np.repeat(np.repeat(grouped==value,16,0),16,1)&visible;alpha=(mask*255).astype('u1');coverage+=mask.astype('u1');layer=im.copy();layer.putalpha(Image.fromarray(alpha,'L'));name=f'{args.scene}_字段{value:04X}_透明.png';layer.save(out/name);assert np.array_equal(np.asarray(layer)[:,:,:3][mask],pixels[:,:,:3][mask])
  tile=Image.new('RGBA',(512,384));td=ImageDraw.Draw(tile)
  for y in range(0,384,16):
   for x in range(0,512,16):td.rectangle((x,y,x+15,y+15),fill='#f7f4ee' if (x//16+y//16)%2 else '#e5e0d6')
  tile.alpha_composite(layer.resize((512,384),Image.Resampling.LANCZOS));xx=(i%3)*512;yy=76+(i//3)*440;preview.paste(tile.convert('RGB'),(xx,yy+38));draw.text((xx+12,yy+8),f'字段 {value:04X} / {int((grouped==value).sum())}格',font=font,fill='#222222')
  rows.append(dict(value=hex(value),file=name,native_cells=int((grouped==value).sum()),visible_pixels=int(mask.sum()),sha256=hashlib.sha256((out/name).read_bytes()).hexdigest()))
 assert np.array_equal(coverage>0,visible) and int(coverage.max())==1;preview.save(out/f'{args.scene}_全部分组预览.png');assert source.read_bytes()==before
 report=dict(scene=args.scene,resource=rid,source=str(source.relative_to(WORK)).replace('\\','/'),source_sha256=hashlib.sha256(before).hexdigest(),grid_sha256=hashlib.sha256(raw).hexdigest(),native_size=[w,h],field_mask=hex(args.mask),groups=rows,export_semantics='flag-field partitions; ground/foreground semantic mapping not established',pixel_rgb_preserved=True,source_origin_preserved=True,only_exact_black_hidden=True,partition_complete_for_nonblack_pixels=True,groups_disjoint=True,game_changed=False)
 (out/'导出说明.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(out/'先看这里.md').write_text(f'# 场景{args.scene}直接分组试导出\n\n先看`{args.scene}_全部分组预览.png`。完整原图和各组透明PNG都在此目录，尺寸{w}×{h}，原点/颜色/比例未改。\n\n这是按原生格字段0x{args.mask:X}直接分组的观察素材，不是已经证实可独立剥离的地面/天花板层。仅将组外和RGB恰好为0的像素隐藏；不重绘、不补出被遮住的地面。全部非黑源像素恰好归属一个组。\n',encoding='utf-8');print(json.dumps(dict(scene=args.scene,groups=len(rows),size=[w,h],partition_complete=True,RGB_preserved=True,game_changed=False)))

if __name__=='__main__':main()
