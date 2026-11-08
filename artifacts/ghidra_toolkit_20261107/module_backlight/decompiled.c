/* provenance: {"address_model": "import address + memory block offset; NOT live VA", "binary": "/mnt/kston/legion-Y70-madness/artifacts/kernel/gki_r59/target_vendor/msm_drm.ko", "command": "decompile", "elf_type": "ET_REL", "filter": "", "ghidra_version": "12.1.4", "selector": "dsi_display_set_backlight", "sha256": "1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804"} */

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

int dsi_display_set_backlight(long param_1,long param_2,uint param_3)

{
  byte bVar1;
  int iVar2;
  code *pcVar3;
  int iVar4;
  ulong uVar5;
  uint *puVar6;
  undefined8 *puVar7;
  uint uVar8;
  
  uVar5 = jiffies_to_msecs(_jiffies);
  if ((param_2 == 0) || (puVar7 = *(undefined8 **)(param_2 + 0x120), puVar7 == (undefined8 *)0x0)) {
    iVar4 = -0x16;
  }
  else {
    mutex_lock(puVar7 + 0x82);
    if ((*(byte *)((long)puVar7 + 0x96d) & 1) == 0) {
      drm_dev_printk(0,&DAT_0016a7ee,"[msm-dsi-info]: Ignor bl_level %u as panel is not init.\n",
                     param_3);
      iVar4 = -0x16;
    }
    else {
      uVar8 = *(uint *)(puVar7 + 0xbd);
      bVar1 = dsi_display_set_backlight_lastTrend;
      if (param_3 != uVar8) {
        bVar1 = 0 < (int)(param_3 - uVar8);
      }
      if ((((param_3 != 0) == (uVar8 == 0)) ||
          (500 < (uVar5 & 0xffffffff) - dsi_display_set_backlight_lasttimejiffies)) ||
         (dsi_display_set_backlight_lastTrend != (bVar1 & 1))) {
        _printk(&DAT_0011cb07,uVar8,param_3,bVar1 & 1,dsi_display_set_backlight_lastTrend,
                *(undefined4 *)(puVar7 + 0xbb),*(undefined4 *)((long)puVar7 + 0x5dc),
                *(undefined8 *)(param_1 + 0x1198),*puVar7);
        dsi_display_set_backlight_lasttimejiffies = uVar5 & 0xffffffff;
      }
      dsi_display_set_backlight_lastTrend = bVar1 & 1;
      iVar4 = *(int *)((long)puVar7 + 0x5ec);
      iVar2 = *(int *)(puVar7 + 0xbe);
      *(uint *)(puVar7 + 0xbd) = param_3;
      uVar8 = (iVar4 * param_3 >> 10) * iVar2;
      if (((0xfffe < uVar8) && (puVar6 = (uint *)puVar7[0xc0], puVar6 != (uint *)0x0)) &&
         (uVar8 / 0xffff < *puVar6)) {
        if (0x1fffdfff < uVar8) {
                    /* WARNING: Does not return */
          pcVar3 = (code *)SoftwareBreakpoint(0x5512,0x347000);
          (*pcVar3)();
        }
        __drm_dev_dbg(0,0,0,
                      "[msm-dsi-debug]: before dimming bl_temp = %llu, after dimming bl_temp = %u\n"
                      ,(ulong)uVar8 / 0xffff,puVar6[(ulong)uVar8 / 0xffff + 1]);
      }
      uVar8 = *(uint *)(puVar7 + 0xbb);
      if (param_3 <= *(uint *)(puVar7 + 0xbb)) {
        uVar8 = param_3;
      }
      if (uVar8 == 0) {
        uVar8 = 0;
      }
      else if (uVar8 <= *(uint *)((long)puVar7 + 0x5d4)) {
        uVar8 = *(uint *)((long)puVar7 + 0x5d4);
      }
      if (*(char *)(param_1 + 0x1568) == '\x01') {
        iVar4 = 0;
        *(uint *)(param_1 + 0x1570) = uVar8;
      }
      else {
        __drm_dev_dbg(0,0,0,"[msm-dsi-debug]: bl_scale = %u, bl_scale_sv = %u, bl_lvl = %u\n",iVar4,
                      iVar2,uVar8);
        iVar4 = dsi_panel_set_backlight(puVar7,uVar8);
        if (iVar4 == 0) {
          iVar4 = 0;
        }
        else {
          drm_dev_printk(0,&DAT_00156cd7,"*ERROR* [msm-dsi-error]: unable to set backlight\n");
        }
      }
    }
    mutex_unlock(puVar7 + 0x82);
  }
  return iVar4;
}


