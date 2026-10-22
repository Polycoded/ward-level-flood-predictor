import { describe, expect, it } from 'vitest';
import { smsInfo } from './sms';

describe('smsInfo', () => {
  it('fits a plain English alert in one 160-character SMS', () => {
    const msg = 'HIGH FLOOD RISK for Velachery. Waterlogging up to knee-deep expected. Rainfall: 120mm. Move to higher ground if needed.';
    expect(smsInfo(msg)).toMatchObject({ encoding: 'GSM-7', segments: 1, singleLimit: 160 });
  });

  it('splits long GSM text at 153 characters per part', () => {
    expect(smsInfo('a'.repeat(161)).segments).toBe(2);
    expect(smsInfo('a'.repeat(306)).segments).toBe(2);
    expect(smsInfo('a'.repeat(307)).segments).toBe(3);
  });

  it('counts GSM extension characters twice', () => {
    expect(smsInfo('€'.repeat(80)).units).toBe(160);
    expect(smsInfo('€'.repeat(81)).segments).toBe(2);
  });

  it('treats Tamil as UCS-2: 70 per SMS, 67 per part', () => {
    const ta = 'கடும் வெள்ள எச்சரிக்கை! ஆபத்தான வெள்ளம். அதிகாரிகள் அறிவுறுத்தினால் உடனே வெளியேறவும்.';
    const info = smsInfo(ta);
    expect(info.encoding).toBe('UCS-2');
    expect(info.singleLimit).toBe(70);
    expect(info.segments).toBe(Math.ceil(ta.length / 67));
    expect(smsInfo('அ'.repeat(70)).segments).toBe(1);
    expect(smsInfo('அ'.repeat(71)).segments).toBe(2);
  });

  it('a single emoji or curly quote forces UCS-2', () => {
    expect(smsInfo('Flood alert ’').encoding).toBe('UCS-2');
  });
});
