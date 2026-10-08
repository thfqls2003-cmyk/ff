-- 설정 (단일 출처)
-- 게임의 모든 숫자(밸런스·치수·카메라·연출)가 여기에 모여 있어요.
-- 숫자를 바꾸면 밸런스가 깨질 수 있으니 조심! (설계서 §3 부등식 재검증 필요)
-- ※ Luau는 변수 이름에 한글을 못 써서 이름은 영어, 설명은 한글 주석으로 달았어요.

local Config = {}

-- [네트워크·입력]
Config.clickRatePerSec = 8   -- 서버 토큰버킷 충전 속도 (초당 최대 8회)
Config.bucketCapacity = 2    -- 순간 버스트 허용치
Config.clientClickGap = 0.125 -- 이보다 빠른 입력은 클라에서 무시 (스윙:신호 1:1)

-- [경제]
Config.startMoney = 50       -- 삭제 금지: 느린 클릭(2회/초)도 60초 안에 첫 업글 보장
Config.critChance = 0.10     -- 10% 확률로 크리티컬
Config.critMult = 3          -- 크리티컬은 데미지 3배

-- [무기 8단계] name=이름, damage=데미지, price=가격, color=이펙트색,
-- swing=스윙 소리키, swingPitch=스윙 피치, hits={{타격 소리키, 피치}...} (레이어)
Config.weapons = {
	{name = "맨주먹",        damage = 1,   price = 0,      color = Color3.fromRGB(255, 204, 153), swing = "whoosh", swingPitch = 1.4,  hits = {{"thud", 1.15}}},
	{name = "나무 망치",     damage = 3,   price = 200,    color = Color3.fromRGB(255, 210, 80),  swing = "whoosh", swingPitch = 1.1,  hits = {{"collide", 1.0}, {"snap", 1.3}}},
	{name = "쇠망치",        damage = 8,   price = 900,    color = Color3.fromRGB(210, 215, 225), swing = "whoosh", swingPitch = 0.9,  hits = {{"collide", 0.7}, {"thud", 0.8}}},
	{name = "소방 도끼",     damage = 20,  price = 4000,   color = Color3.fromRGB(230, 235, 255), swing = "slash",  swingPitch = 0.85, hits = {{"snap", 0.6}, {"collide", 0.9}}},
	{name = "전기톱",        damage = 50,  price = 15000,  color = Color3.fromRGB(255, 160, 50),  swing = "whoosh", swingPitch = 1.2,  hits = {{"snap", 1.4}, {"step", 1.6}}},
	{name = "착암 드릴",     damage = 125, price = 55000,  color = Color3.fromRGB(150, 200, 255), swing = "whoosh", swingPitch = 1.0,  hits = {{"splash", 1.6}, {"snap", 1.1}}},
	{name = "로켓 펀치",     damage = 320, price = 200000, color = Color3.fromRGB(255, 120, 60),  swing = "lunge",  swingPitch = 0.8,  hits = {{"splash", 0.5}, {"collide", 0.5}, {"thud", 0.6}}},
	{name = "황금 로켓펀치", damage = 800, price = 750000, color = Color3.fromRGB(255, 200, 60),  swing = "lunge",  swingPitch = 0.7,  hits = {{"splash", 0.5}, {"collide", 0.5}, {"ping", 0.5}}},
}

-- [강화: 8단계 이후 무한] n = 강화 레벨(1, 2, 3, ...)
Config.enhance = { baseDamage = 800, damageMult = 1.3, basePrice = 750000, priceMult = 1.35 }
function Config.enhanceDamage(n)
	return math.floor(Config.enhance.baseDamage * Config.enhance.damageMult ^ n + 0.5)
end
function Config.enhancePrice(n)
	return math.floor(Config.enhance.basePrice * Config.enhance.priceMult ^ n)
end

-- [건물·돈 곡선] s = 스테이지(1부터 무한). HP·돈은 number 그대로(math.floor 외 변환 금지)
function Config.buildingHP(s)
	return math.floor(100 * 1.45 ^ (s - 1) + 0.5)
end
function Config.moneyValue(s)
	return 1.12 ^ (s - 1)
end
function Config.destroyBonus(s)
	return math.floor(0.5 * Config.buildingHP(s) * Config.moneyValue(s) + 0.5)
end
-- 타격당 지급 = math.max(1, math.floor(math.min(데미지, 남은HP) * Config.moneyValue(s)))

-- [건물 치수] 폭이 고정이라 카메라는 높이만 보고 결정됨
Config.building = {
	width = 24,
	depth = 14,
	floorHeight = 6,
	blockSize = Vector3.new(12, 6, 7),  -- 층당 2x2 = 4블록, 중심 x = ±6, z = ±3.5
	roofSize = Vector3.new(25, 1, 15),
}
function Config.floorCount(s)
	return math.min(3 + s, 12)  -- 최대 12층 → 파트 49개 상한
end

-- [팔레트] (s-1) % 8 + 1 로 순환: {벽색, 지붕색}
Config.palettes = {
	{Color3.fromRGB(226, 214, 181), Color3.fromRGB(142, 100, 74)},  -- 벽돌상가
	{Color3.fromRGB(176, 196, 222), Color3.fromRGB(90, 104, 130)},  -- 오피스
	{Color3.fromRGB(222, 170, 160), Color3.fromRGB(120, 70, 70)},   -- 빨간벽돌
	{Color3.fromRGB(190, 190, 200), Color3.fromRGB(80, 80, 90)},    -- 콘크리트
	{Color3.fromRGB(170, 210, 190), Color3.fromRGB(70, 120, 95)},   -- 민트
	{Color3.fromRGB(235, 200, 140), Color3.fromRGB(160, 120, 60)},  -- 노란상가
	{Color3.fromRGB(150, 160, 185), Color3.fromRGB(60, 70, 100)},   -- 고층빌딩
	{Color3.fromRGB(210, 180, 220), Color3.fromRGB(120, 90, 140)},  -- 보라호텔
}

-- [카메라] 건물 높이 Hb = 층수 × 6
Config.camera = { FOV = 50 }
function Config.cameraY(Hb)
	return Hb * 0.45 + 4
end
function Config.cameraZ(Hb)
	return math.max(55, Hb * 1.35 + 30)
end
-- 주시점 = Vector3.new(0, Hb*0.42, 0). 추적: pos = pos:Lerp(목표, 1 - 0.0005^dt)

-- [셰이크] Shake(mag): shakeMag = max(shakeMag, mag), 매 프레임 ×0.88^(dt*60)
Config.shake = { hit = 0.4, crit = 0.9, bigWeapon = 1.4, collapse = 2.2 }  -- bigWeapon = 무기 7·8단계

-- [붕괴 타이밍]
Config.collapse = { physicsDelay = 0.15, debrisLife = 3.0, rebuildDelay = 3.5 }

-- [파손 문턱] HP 비율이 아래로 통과하는 순간 1회씩 발동
Config.damageThresholds = { 0.66, 0.33 }

-- [저장]
Config.save = { storeName = "건물부수기_v1", autoSaveSec = 120, retries = 3 }

-- [돈 표시] 10만 미만은 콤마, 그 이상은 만/억/조 축약 (예: 1366875 → "136.6만")
local UNITS = {
	{1e12, "조"},
	{1e8, "억"},
	{1e4, "만"},
}

-- 정수에 천 단위 콤마 찍기
function Config.comma(n)
	local s = tostring(math.floor(n))
	local sign = ""
	if s:sub(1, 1) == "-" then
		sign = "-"
		s = s:sub(2)
	end
	local out = s:reverse():gsub("(%d%d%d)", "%1,"):reverse():gsub("^,", "")
	return sign .. out
end

function Config.formatMoney(n)
	n = math.floor(n)
	if n < 100000 then
		return Config.comma(n)
	end
	for _, pair in ipairs(UNITS) do
		local base, label = pair[1], pair[2]
		if n >= base then
			local v = n / base
			local text = string.format("%.1f", v)  -- 소수 첫째 자리 반올림 (1366875 → 136.7만)
			text = text:gsub("%.0$", "")           -- 끝이 .0이면 떼기
			return text .. label
		end
	end
	return Config.comma(n)
end

return Config
