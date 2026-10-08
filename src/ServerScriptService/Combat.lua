-- 전투 (서버)
-- 클라의 "쳤다" 신호를 받아 레이트리밋 → 데미지·크리 계산 → 돈 지급 →
-- HP 차감 → 연출 브로드캐스트 → 붕괴까지 이어지는 핵심 흐름이에요.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Game"):WaitForChild("Config"))

local Combat = {}

local building = nil
local economy = nil
local remotes = nil

-- 플레이어별 토큰버킷: [player] = {tokens, lastTime}
local buckets = {}
-- 이번 건물을 때린 사람들 (파괴 보너스용): [userId] = player
local hitters = {}

local connections = {}

-- 토큰버킷: 용량 2, 초당 8 충전. 초과분은 조용히 드롭 (킥·경고 금지 — 랙 유저 보호)
local function takeToken(player)
	local now = os.clock()
	local b = buckets[player]
	if not b then
		b = { tokens = Config.bucketCapacity, lastTime = now }
		buckets[player] = b
	end
	local elapsed = now - b.lastTime
	b.lastTime = now
	b.tokens = math.min(Config.bucketCapacity, b.tokens + elapsed * Config.clickRatePerSec)
	if b.tokens >= 1 then
		b.tokens -= 1
		return true
	end
	return false
end

-- 붕괴 시퀀스
local function doCollapse()
	local s = building.GetStage()
	local _, maxHp = building.GetHP()
	building.SetState("붕괴중")  -- 이후 Hit은 전부 드롭

	-- 보너스: 타격자 전원에게 각자 전액 지급 + bestStage 갱신
	local bonus = Config.destroyBonus(s)
	for _, p in pairs(hitters) do
		if p.Parent then
			economy.Award(p, bonus)
			economy.UpdateBestStage(p, s + 1)
		end
	end
	hitters = {}

	-- 전원에게 붕괴 알림 (bonus = 참여자 1인당 보너스)
	remotes.Stage:FireAllClients("collapse", s, 0, maxHp, bonus)

	-- 잠깐 뒤 물리 와르르
	task.delay(Config.collapse.physicsDelay, function()
		building.StartCollapse()
	end)

	-- 잔해가 사라진 뒤(3.0초) 새 건물 (3.5초)
	task.delay(Config.collapse.rebuildDelay, function()
		local newMax = building.BuildStage(s + 1)
		remotes.Stage:FireAllClients("new", s + 1, newMax, newMax, 0)
	end)
end

-- Hit 1회 처리
local function onHit(player)
	-- 1) 레이트리밋
	if not takeToken(player) then
		return
	end
	-- 2) 건물 상태 확인
	if building.GetState() ~= "전투" then
		return
	end
	-- 2.5) 저장 로드가 끝난(세션 준비된) 플레이어만 (접속 직후 레이스 방지)
	if not economy.GetState(player) then
		return
	end

	-- 3) 데미지·크리 계산 (전부 서버)
	local damage = economy.GetDamage(player)
	local isCrit = math.random() < Config.critChance
	if isCrit then
		damage *= Config.critMult
	end

	-- 4) 돈 지급: max(1, floor(min(데미지, 남은HP) × 돈가치))
	local s = building.GetStage()
	local hp = building.GetHP()
	local pay = math.max(1, math.floor(math.min(damage, hp) * Config.moneyValue(s)))
	economy.Award(player, pay)

	-- 5) HP 차감 + 타격자 기록
	local newHp = building.ApplyDamage(damage)
	hitters[player.UserId] = player

	-- 6) 연출 브로드캐스트 (수락된 타격당 1발 → 인당 최대 8/s)
	local hitPos = building.GetHitPos()
	local _, maxHp = building.GetHP()
	remotes.HitFx:FireAllClients(player.UserId, damage, isCrit, hitPos, newHp, maxHp)

	-- 7) 붕괴?
	if newHp <= 0 then
		doCollapse()
	end
end

-- 타격자 기록 초기화 (건물을 통째로 교체할 때 호출 — 이전 건물 타격은 무효)
function Combat.ResetHitters()
	hitters = {}
end

function Combat.Init(buildingModule, economyModule, remotesTable)
	building = buildingModule
	economy = economyModule
	remotes = remotesTable

	table.insert(connections, remotes.Hit.OnServerEvent:Connect(onHit))

	table.insert(connections, Players.PlayerRemoving:Connect(function(player)
		buckets[player] = nil
		hitters[player.UserId] = nil
	end))
end

return Combat
