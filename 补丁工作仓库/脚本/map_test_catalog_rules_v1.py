"""Curated test-map eligibility; retain raw exports, filter nonplayable illustration/credits entries."""
NON_MAP_SCENES=frozenset(range(835,878))
EMPTY_COPIES={832:(192,'锁链桥'),833:(203,'锁妖塔第九层'),834:(205,'锁妖塔第十一层')}

def testable(scene):
 return scene not in NON_MAP_SCENES

def display_name(scene,resource,native_name):
 if native_name and native_name.strip():return native_name
 row=EMPTY_COPIES.get(scene)
 if row and row[0]==resource:return row[1]+'（空布置副本，用途待核）'
 return f'未命名场景（资源{resource}，用途待核）'
