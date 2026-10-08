-- 경제 (서버)
-- 플레이어별 돈·무기단계·강화·최고스테이지를 관리해요.
-- leaderstats "돈"과 Attribute(WeaponId/EnhLevel/BestStage)로 클라에 자동 복제돼요.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Game"):WaitForChild("Config"))

local Economy = {}

-- 플레이어별 세션 상태: [player] = {money, tier, enh, bestStage, loadFailed}
local sessions = {}

function Economy.Init()
	sessions = {}
end

-- 접속한 플레이어 세팅 (저장 데이터 또는 기본값으로)
function Economy.AddPlayer(player, data)
	data = data or {}
	local s = {
		money = data.money or Config.startMoney,
		tier = math.clamp(data.tier or 1, 1, #Config.weapons),
		enh = math.max(0, data.enh or 0),
		bestStage = math.max(1, data.bestStage or 1),
		loadFailed = data.loadFailed or false,
	}
	sessions[player] = s

	-- leaderstats (플레이어 목록에 돈 표시 + 자동 복제)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local moneyValue = Instance.new("IntValue")
	moneyValue.Name = "돈"
	moneyValue.Value = math.floor(s.money)
	moneyValue.Parent = stats
	stats.Parent = player

	-- Attribute 복제
	player:SetAttribute("WeaponId", s.tier)
	player:SetAttribute("EnhLevel", s.enh)
	player:SetAttribute("BestStage", s.bestStage)

	return s
end

function Economy.RemovePlayer(player)
	sessions[player] = nil
end

-- 현재 상태 읽기 (저장용)
function Economy.GetState(player)
	return sessions[player]
end

-- leaderstats 갱신 도우미
local function refreshMoney(player, s)
	local stats = player:FindFirstChild("leaderstats")
	if stats then
		local moneyValue = stats:FindFirstChild("돈")
		if moneyValue then
			moneyValue.Value = math.floor(s.money)
		end
	end
end

-- 돈 지급 (반드시 이 함수 경유)
function Economy.Award(player, amount)
	local s = sessions[player]
	if not s or amount <= 0 then
		return
	end
	s.money += amount
	refreshMoney(player, s)
end

-- 플레이어의 현재 공격 데미지 (무기 + 강화)
function Economy.GetDamage(player)
	local s = sessions[player]
	if not s then
		return 1
	end
	if s.tier >= #Config.weapons and s.enh > 0 then
		return Config.enhanceDamage(s.enh)
	end
	return Config.weapons[s.tier].damage
end

-- 최고 스테이지 갱신
function Economy.UpdateBestStage(player, stage)
	local s = sessions[player]
	if s and stage > s.bestStage then
		s.bestStage = stage
		player:SetAttribute("BestStage", stage)
	end
end

-- 구매 처리 (항상 "다음 단계" — 클라가 뭘 고를 수 없어 안전)
-- 반환: ok, msg, money, tier, enh
function Economy.Buy(player)
	local s = sessions[player]
	if not s then
		return false, "잠깐만요, 아직 준비 중이에요", 0, 1, 0
	end

	if s.tier < #Config.weapons then
		-- 다음 무기 구매
		local nextWeapon = Config.weapons[s.tier + 1]
		if s.money < nextWeapon.price then
			return false, "돈이 부족해요!", math.floor(s.money), s.tier, s.enh
		end
		s.money -= nextWeapon.price
		s.tier += 1
		refreshMoney(player, s)
		player:SetAttribute("WeaponId", s.tier)
		return true,
			string.format("%s 구매! -%s원", nextWeapon.name, Config.comma(nextWeapon.price)),
			math.floor(s.money), s.tier, s.enh
	else
		-- 8단계 이후: 강화 (무한)
		local price = Config.enhancePrice(s.enh + 1)
		if s.money < price then
			return false, "돈이 부족해요!", math.floor(s.money), s.tier, s.enh
		end
		s.money -= price
		s.enh += 1
		refreshMoney(player, s)
		player:SetAttribute("EnhLevel", s.enh)
		return true,
			string.format("황금 로켓펀치 +%d 강화! -%s원", s.enh, Config.formatMoney(price)),
			math.floor(s.money), s.tier, s.enh
	end
end

return Economy
