package com.assetmind.server_auth.user.domain.port;

import java.util.UUID;

/**
 * 도메인의 식별자 생성 전략을 정의하는 인터페이스
 * 도메인 계층은 어떤 기술을 사용하여 자신의 ID가 생성되는지 알 필요없이
 * 해당 인터페이스를 통 식별자를 주입받아 사용
 * 이를 통해
 * 도메인이 외부 기술을 몰라도 되는 도메인의 순수성을 충족시킬 수 있고,
 * DIP(의존성 역전 원칙)을 달성하게 되고
 * 도메인이 구체적인 기술에 의존하지 않으므로 확장성 있는 설계가 가능하다.
 */
public interface UserIdGenerator {

    /**
     * 새로운 User ID를 생성
     * @return 생성된 UUID
     */
    UUID generate();

}
