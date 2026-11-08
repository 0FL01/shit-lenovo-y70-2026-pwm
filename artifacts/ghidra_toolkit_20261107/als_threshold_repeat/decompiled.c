/* provenance: {"address_model": "import address + memory block offset; NOT live VA", "binary": "/mnt/kston/legion-Y70-madness/artifacts/current_display_path/als/motorola.hardware.sensorext-service", "command": "decompile", "elf_type": "ET_DYN", "filter": "", "ghidra_version": "12.1.4", "selector": "_ZN15AlsCompensation9calculateEfj", "sha256": "b1a3bbb2dcb2fc975403c40df5a8404f62d3c95ac7239f5cdc2b0c05a7643f71"} */

/* WARNING: Removing unreachable block (ram,0x00114ca4) */
/* AlsCompensation::calculate(float, unsigned int) */

float __thiscall AlsCompensation::calculate(AlsCompensation *this,float param_1,uint param_2)

{
  uint uVar1;
  AlsCompensation *pAVar2;
  short *psVar3;
  undefined4 uVar4;
  long lVar5;
  float *__src;
  uint uVar6;
  uchar *puVar7;
  void *__dest;
  char *pcVar8;
  ulong uVar9;
  uint uVar10;
  float fVar11;
  float fVar12;
  float fVar13;
  float fVar14;
  double dVar15;
  undefined8 uVar16;
  undefined8 uVar17;
  undefined8 uVar18;
  undefined8 uVar19;
  undefined8 in_stack_fffffffffffffec8;
  undefined4 uVar21;
  undefined8 uVar20;
  undefined8 in_stack_fffffffffffffed0;
  undefined4 uVar23;
  undefined8 uVar22;
  undefined4 uVar24;
  void *local_f0;
  long local_e8;
  long local_e0;
  void *local_d8;
  long local_d0;
  long local_c8;
  float *local_c0;
  float *local_b8;
  long local_b0;
  undefined8 local_a8;
  ulong local_a0;
  short *local_98;
  long local_90;
  
  uVar23 = (undefined4)((ulong)in_stack_fffffffffffffed0 >> 0x20);
  uVar21 = (undefined4)((ulong)in_stack_fffffffffffffec8 >> 0x20);
  lVar5 = tpidr_el0;
  local_90 = *(long *)(lVar5 + 0x28);
  fVar13 = *(float *)(this + 0xf8);
  uVar6 = DisplayBuffer::getBrightness(*(DisplayBuffer **)(this + 0x48));
  uVar10 = *(uint *)(this + 0xd8);
  if ((uVar6 <= *(uint *)(this + 0xd8)) &&
     (uVar9 = (ulong)uVar6, uVar10 = uVar6, this[0x5020] == (AlsCompensation)0x1)) {
    __android_log_print(3,"SENSOREXT_ALS_COMP",
                        "Need corresponding backlight array due to screen setting, read backlight %d, corresponding backlight %d"
                        ,uVar9,*(undefined4 *)(this + uVar9 * 4 + 0x200));
    uVar10 = *(uint *)(this + uVar9 * 4 + 0x200);
  }
  local_a8 = 0;
  local_a0 = 0;
  local_98 = (short *)0x0;
  DisplayBuffer::getDpms();
  uVar6 = DisplayBuffer::getDCmode(*(DisplayBuffer **)(this + 0x48));
  uVar9 = local_a8 >> 1 & 0x7f;
  if ((local_a8 & 1) != 0) {
    uVar9 = local_a0;
  }
  if (uVar9 == 3) {
    psVar3 = local_98;
    if ((local_a8 & 1) == 0) {
      psVar3 = (short *)((long)&local_a8 + 1);
    }
    if (*psVar3 != 0x664f || (char)psVar3[1] != 'f') goto LAB_001148c0;
  }
  else {
LAB_001148c0:
    fVar11 = param_1 * fVar13;
    if ((uVar10 != 0) && (fVar11 <= *(float *)(this + 0xf4))) {
      uVar1 = 0;
      if (uVar10 <= *(int *)(this + 0xf0) - 1U) {
        uVar1 = uVar6;
      }
      puVar7 = (uchar *)DisplayBuffer::getRGB
                                  (*(DisplayBuffer **)(this + 0x48),*(int *)(this + 0xe0),
                                   *(int *)(this + 0xdc),*(int *)(this + 0xe4),*(int *)(this + 0xe8)
                                  );
      if (puVar7 == (uchar *)0x0) {
        __android_log_print(3,"SENSOREXT_ALS_COMP","screenshot error, not report lux");
        if (this[0x100] == (AlsCompensation)0x1) {
          __android_log_print(3,"SENSOREXT_ALS_COMP","factory version return pre report lux");
          fVar14 = *(float *)(this + 0x80);
        }
        else {
          fVar14 = -1.0;
          *(undefined4 *)(this + 0x80) = 0xbf800000;
        }
        goto LAB_00114ccc;
      }
      fVar13 = (float)NEON_ucvtf(*(undefined4 *)(this + 0xd8));
      local_c0 = (float *)0x0;
      local_b8 = (float *)0x0;
      local_b0 = 0;
      PanelLux::getPanelLux
                (*(PanelLux **)(this + 0x50),(float)uVar10 / fVar13,param_2,uVar1,puVar7,
                 *(int *)(this + 0x138),*(int *)(this + 0x13c));
      __src = local_c0;
      fVar13 = *(float *)(this + 0xf8);
      if (*(int *)(this + 0x144) == 0) {
        local_f0 = (void *)0x0;
        local_e8 = 0;
        local_e0 = 0;
        uVar9 = (long)local_b8 - (long)local_c0;
        if (uVar9 != 0) {
          if ((long)uVar9 < 0) {
                    /* WARNING: Subroutine does not return */
            std::
            vector<SensorChanelCal::MultiDbvChData,std::allocator<SensorChanelCal::MultiDbvChData>>
            ::__throw_length_error_abi_nn200000_();
          }
          __dest = operator_new(uVar9);
          local_f0 = __dest;
          local_e0 = (long)__dest + uVar9;
          memcpy(__dest,__src,uVar9);
          local_e8 = (long)__dest + uVar9;
          fVar14 = (float)SensorChanelCal::getCompAlsByCh
                                    ((SensorChanelCal *)(this + 0x140),&local_f0,uVar10,uVar1,1);
          goto LAB_00114acc;
        }
        fVar14 = (float)SensorChanelCal::getCompAlsByCh
                                  ((SensorChanelCal *)(this + 0x140),&local_f0,uVar10,uVar1,1);
      }
      else {
        local_d8 = (void *)0x0;
        local_d0 = 0;
        local_c8 = 0;
        uVar9 = (long)local_b8 - (long)local_c0;
        if (uVar9 == 0) {
          fVar14 = (float)SensorChanelCal::getCompAlsByGoodix
                                    ((SensorChanelCal *)(this + 0x140),&local_d8,uVar10,uVar1,0,
                                     param_2);
        }
        else {
          if ((long)uVar9 < 0) {
                    /* WARNING: Subroutine does not return */
            std::
            vector<SensorChanelCal::MultiDbvChData,std::allocator<SensorChanelCal::MultiDbvChData>>
            ::__throw_length_error_abi_nn200000_();
          }
          __dest = operator_new(uVar9);
          local_d8 = __dest;
          local_c8 = (long)__dest + uVar9;
          memcpy(__dest,__src,uVar9);
          local_d0 = (long)__dest + uVar9;
          fVar14 = (float)SensorChanelCal::getCompAlsByGoodix
                                    ((SensorChanelCal *)(this + 0x140),&local_d8,uVar10,uVar1,0,
                                     param_2);
LAB_00114acc:
          operator_delete(__dest,uVar9);
        }
      }
      fVar13 = fVar13 * fVar14;
      if (*(code **)(this + 0x60) == (code *)0x0) {
        fVar14 = fVar11 - fVar13;
      }
      else {
        fVar14 = (float)(**(code **)(this + 0x60))
                                  (fVar11,fVar13,*(undefined4 *)(this + 0x80),this[0x100],
                                   *(undefined4 *)(this + 0x84),uVar1);
      }
      SensorChanelCal::getFacChCoefByDbv((int)this + 0x140,uVar10);
      fVar12 = *(float *)(this + 0x5028);
      if (fVar12 == 0.0) {
        fVar14 = fVar14 + (float)*(int *)(this + 0x5024);
      }
      else if (fVar14 < fVar12) {
        fVar14 = fVar12;
      }
      pAVar2 = this + 0x29;
      if (((byte)this[0x28] & 1) != 0) {
        pAVar2 = *(AlsCompensation **)(this + 0x38);
      }
      if (*(int *)(this + 0x144) == 0) {
        dVar15 = *(double *)(this + 0x1d8);
        pcVar8 = 
        "%s: ReportLux %.2f (%.2f-%.2f), pre %.2f, dbv %d, dc %d, fps %d, chPanel %.2f-%.2f-%.2f-%.2f, facCal:lux_s %.2f cha_s %.2f-%.2f-%.2f-%.2f, RunInfo: DPB %d-%d, TF %d-%d"
        ;
        uVar4 = *(undefined4 *)(*(long *)(this + 0x48) + 0xb8);
        uVar24 = (*(undefined4 **)(this + 0x50))[1];
        uVar20 = CONCAT44(uVar21,*(undefined4 *)(*(long *)(this + 0x48) + 0xbc));
        uVar22 = CONCAT44(uVar23,**(undefined4 **)(this + 0x50));
        uVar16 = uRam0000000000000000;
        uVar17 = uRam0000000000000008;
        uVar18 = uRam0000000000000010;
        uVar19 = uRam0000000000000018;
      }
      else {
        pcVar8 = 
        "%s: ReportLux %.2f (%.2f-%.2f), pre %.2f, dbv %d, dc %d, fps %d, chPanel %.2f-%.2f-%.2f-%.2f-%.2f, facCal:lux_s %.2f cha_s %.2f-%.2f-%.2f-%.2f-%.2f, RunInfo: DPB %d-%d, TF %d-%d"
        ;
        uVar4 = *(undefined4 *)(*(long *)(this + 0x48) + 0xb8);
        uVar24 = *(undefined4 *)(*(long *)(this + 0x48) + 0xbc);
        dVar15 = (double)local_c0[4];
        uVar16 = *(undefined8 *)(this + 0x1d8);
        uVar17 = uRam0000000000000000;
        uVar18 = uRam0000000000000008;
        uVar19 = uRam0000000000000010;
        uVar20 = uRam0000000000000018;
        uVar22 = uRam0000000000000020;
      }
      __android_log_print((double)fVar14,(double)fVar11,(double)fVar13,
                          (double)*(float *)(this + 0x80),(double)*local_c0,(double)local_c0[1],
                          (double)local_c0[2],(double)local_c0[3],3,"SENSOREXT_ALS_COMP",pcVar8,
                          pAVar2,uVar10,uVar1,param_2,uVar4,dVar15,uVar16,uVar17,uVar18,uVar19,
                          uVar20,uVar22,uVar24);
      *(float *)(this + 0x80) = fVar14;
      if (local_c0 != (float *)0x0) {
        local_b8 = local_c0;
        operator_delete(local_c0,local_b0 - (long)local_c0);
      }
      goto LAB_00114ccc;
    }
  }
  fVar13 = param_1 * fVar13;
  fVar11 = *(float *)(this + 0x5028);
  fVar14 = 0.1;
  if (DAT_00105920 <= (double)fVar13) {
    fVar14 = fVar13;
  }
  if (fVar11 == 0.0) {
    fVar14 = fVar14 + (float)*(int *)(this + 0x5024);
  }
  else if (fVar14 < fVar11) {
    fVar14 = fVar11;
  }
  pAVar2 = this + 0x29;
  if (((byte)this[0x28] & 1) != 0) {
    pAVar2 = *(AlsCompensation **)(this + 0x38);
  }
  psVar3 = local_98;
  if ((local_a8 & 1) == 0) {
    psVar3 = (short *)((long)&local_a8 + 1);
  }
  __android_log_print((double)fVar14,3,"SENSOREXT_ALS_COMP",
                      "%s: no calculate, ReportLux %.2f, dpms: %s, dbv %d",pAVar2,psVar3,uVar10);
  *(float *)(this + 0x80) = fVar14;
LAB_00114ccc:
  if ((local_a8 & 1) != 0) {
    operator_delete(local_98,local_a8 & 0xfffffffffffffffe);
  }
  if (*(long *)(lVar5 + 0x28) == local_90) {
    return fVar14;
  }
                    /* WARNING: Subroutine does not return */
  __stack_chk_fail();
}


