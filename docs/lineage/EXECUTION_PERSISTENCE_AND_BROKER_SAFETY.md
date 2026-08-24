# 주문 실행·브로커·영속성·복구

- V1~V5는 deal publication 지연, 보호 확인, 재조정, 연결단절, 단일 소유권, alternating state, event rotation 문제를 순차적으로 수정했다.
- B48/V6은 RC4 압축을 통합했고 B49/V6R2는 Shadow catch-up, B52/V6R3는 gap complete, B66/V6R4는 cursor checkpoint, B67/V6R5는 activation seal, B70/V6R6은 단일 transient modify retry를 추가했다.
- B70 V6R6만 기존 Terminus에서 Live 권한을 가진다. Next Live는 별도 권한 전까지 비활성이다.
- NEXT-E01/V7은 이 계보를 모듈로 분리하지만 주문 순서·rounding·저널·reconciliation·보호·fail-closed 의미를 바꾸지 않는다.

