-- 저장 (서버)
-- DataStore로 돈·무기·강화·최고스테이지를 저장해요. 전부 pcall로 감싸서
-- 스튜디오에서 API가 꺼져 있어도 게임은 멀쩡하게 돌아가요 (기본 테스트 시나리오).

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Config = require(ReplicatedStorage:WaitForChild("Game"):WaitForChild("Config"))

local SaveData = {}

local store = nil
local economy = nil

function SaveData.Init(economyModule)
	economy = economyModule
	-- 스토어 가져오기 자체도 실패할 수 있음 (스튜디오 API 꺼짐 등)
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(Config.save.storeName)
	end)
	if ok then
		store = result
	else
		warn("[저장] DataStore를 못 열었어요 — 저장 없이 진행합니다:", result)
	end
end

local function keyFor(player)
	return "p_" .. player.UserId
end

-- 로드: pcall 최대 3회 재시도, 실패 간 2초 대기
-- 전부 실패하면 기본값 + loadFailed=true (좋은 데이터 덮어쓰기 방지)
function SaveData.Load(player)
	local default = { money = Config.startMoney, tier = 1, enh = 0, bestStage = 1, loadFailed = false }
	if not store then
		-- 스튜디오라 저장 안 됨 — 기본값으로 정상 진행
		warn("[저장] 스튜디오라 저장 안 됨 — 기본값으로 시작해요")
		return default
	end

	for attempt = 1, Config.save.retries do
		local ok, data = pcall(function()
			return store:GetAsync(keyFor(player))
		end)
		if ok then
			if data and type(data) == "table" then
				return {
					money = tonumber(data.money) or Config.startMoney,
					tier = tonumber(data.tier) or 1,
					enh = tonumber(data.enh) or 0,
					bestStage = tonumber(data.bestStage) or 1,
					loadFailed = false,
				}
			end
			return default  -- 데이터 없음 = 새 플레이어
		end
		if attempt < Config.save.retries then
			task.wait(2)
		end
	end

	-- 전부 실패: 기본값으로 놀되, 저장은 절대 안 함
	warn("[저장] 로드 실패 — 이번 세션은 저장을 건너뜁니다 (" .. player.Name .. ")")
	default.loadFailed = true
	return default
end

-- 저장: UpdateAsync 1회 (pcall). loadFailed면 무조건 건너뜀.
function SaveData.Save(player)
	if not store or not economy then
		return
	end
	local s = economy.GetState(player)
	if not s or s.loadFailed then
		return  -- 좋은 데이터를 덮어쓰면 안 돼요
	end
	local payload = {
		v = 1,
		money = math.floor(s.money),
		tier = s.tier,
		enh = s.enh,
		bestStage = s.bestStage,
		savedAt = os.time(),
	}
	local ok, err = pcall(function()
		store:UpdateAsync(keyFor(player), function(old)
			-- 다른 서버가 먼저 저장한 데이터가 있으면 덮어쓰지 않게 병합해요
			-- (서버 A 저장 지연 사이에 서버 B가 진행한 내용 보호 — lost-update 방지)
			if type(old) == "table" then
				if (tonumber(old.savedAt) or 0) > payload.savedAt then
					return old  -- 저쪽이 더 최신이면 그대로 유지
				end
				-- 진행도는 필드별로 더 높은 쪽 유지 (돈은 소비가 정상이라 병합 제외)
				payload.tier = math.max(payload.tier, tonumber(old.tier) or 1)
				payload.enh = math.max(payload.enh, tonumber(old.enh) or 0)
				payload.bestStage = math.max(payload.bestStage, tonumber(old.bestStage) or 1)
			end
			return payload
		end)
	end)
	if not ok then
		warn("[저장] 저장 실패 (" .. player.Name .. "):", err)
	end
end

-- 자동저장(120초) + 서버 종료 시 전원 저장
function SaveData.StartAutoSave()
	task.spawn(function()
		while true do
			task.wait(Config.save.autoSaveSec)
			for _, p in ipairs(Players:GetPlayers()) do
				SaveData.Save(p)
			end
		end
	end)

	game:BindToClose(function()
		if RunService:IsStudio() and not store then
			return
		end
		-- 전원 동기 저장 (BindToClose 안에서는 기다려도 됨)
		for _, p in ipairs(Players:GetPlayers()) do
			SaveData.Save(p)
		end
	end)
end

return SaveData
