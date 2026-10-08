-- 메인 (서버 진입점 — 유일한 Script)
-- 월드 → 리모트 → 저장 → 경제 → 건물 → 전투 순서로 켜고,
-- 플레이어 접속/퇴장과 캐릭터 받침대 고정을 처리해요.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local World = require(script.Parent.World)
local Building = require(script.Parent.Building)
local Combat = require(script.Parent.Combat)
local Economy = require(script.Parent.Economy)
local SaveData = require(script.Parent.SaveData)

local GameFolder = ReplicatedStorage:WaitForChild("Game")

-- 1) 월드 생성 (땅·배경·받침대·조명·충돌그룹)
World.Build()

-- 2) 리모트 생성 (속성 다 정하고 마지막에 Parent)
local Remotes = {}
do
	local folder = Instance.new("Folder")
	folder.Name = "Remotes"

	local hit = Instance.new("RemoteEvent")
	hit.Name = "Hit"
	hit.Parent = folder

	local hitFx = Instance.new("RemoteEvent")
	hitFx.Name = "HitFx"
	hitFx.Parent = folder

	local stage = Instance.new("RemoteEvent")
	stage.Name = "Stage"
	stage.Parent = folder

	local ready = Instance.new("RemoteEvent")
	ready.Name = "Ready"
	ready.Parent = folder

	local buy = Instance.new("RemoteFunction")
	buy.Name = "Buy"
	buy.Parent = folder

	folder.Parent = GameFolder

	Remotes.Hit = hit
	Remotes.HitFx = hitFx
	Remotes.Stage = stage
	Remotes.Ready = ready
	Remotes.Buy = buy
end

-- 3) 저장·경제 초기화
SaveData.Init(Economy)
Economy.Init()

-- 4) 첫 건물
Building.BuildStage(1)
local firstPlayerApplied = false  -- 첫 접속자의 bestStage로 시작 스테이지 재설정(서버당 1회)

-- 5) 전투 연결
Combat.Init(Building, Economy, Remotes)

-- 6) 구매 핸들러 (RemoteFunction은 C→S 한 방향만)
Remotes.Buy.OnServerInvoke = function(player)
	return Economy.Buy(player)
end

-- 7) 클라 준비 핸드셰이크: 클라가 Stage 핸들러 연결을 마치고 신호를 보내면
--    현재 건물 상태를 보내줘요 (접속 직후 보낸 sync가 유실돼도 안전)
Remotes.Ready.OnServerEvent:Connect(function(player)
	local hp, maxHp = Building.GetHP()
	Remotes.Stage:FireClient(player, "sync", Building.GetStage(), hp, maxHp, 0)
end)

-- 플레이어별 연결 보관 (누수 방지)
local playerConns = {}

-- 받침대 슬롯 관리 (접속 순서 할당, 퇴장 반납)
local usedSlots = {}  -- [slot] = player
local function takeSlot(player)
	for slot = 0, 7 do
		if not usedSlots[slot] then
			usedSlots[slot] = player
			return slot
		end
	end
	return 0
end
local function releaseSlot(player)
	for slot, p in pairs(usedSlots) do
		if p == player then
			usedSlots[slot] = nil
		end
	end
end

-- 캐릭터를 받침대에 앵커 고정 (낙하·잔해 탑승·밀림 사고 원천 차단)
local function pinCharacter(player, character, slot)
	local conns = playerConns[player]
	if not conns then
		return
	end

	-- 캐릭터 모든 파트를 "플레이어" 충돌그룹으로 (잔해와 비충돌)
	local function setGroup(inst)
		if inst:IsA("BasePart") then
			inst.CollisionGroup = "플레이어"
		end
	end
	for _, d in ipairs(character:GetDescendants()) do
		setGroup(d)
	end
	local descConn = character.DescendantAdded:Connect(setGroup)
	table.insert(conns, descConn)
	-- Once라 리스폰마다 연결이 쌓이지 않고 1회 실행 후 스스로 사라져요
	player.CharacterRemoving:Once(function()
		descConn:Disconnect()
	end)

	local hrp = character:WaitForChild("HumanoidRootPart", 10)
	local humanoid = character:WaitForChild("Humanoid", 10)
	if not hrp or not humanoid then
		return
	end

	-- 받침대 위에서 건물(x=0, z=0) 쪽 바라보기
	local pos = World.PadPosition(slot)
	local standAt = Vector3.new(pos.X, pos.Y + 1.5, pos.Z)
	local lookAt = Vector3.new(0, standAt.Y, 0)
	character:PivotTo(CFrame.lookAt(standAt, lookAt))

	hrp.Anchored = true
	humanoid.WalkSpeed = 0
	humanoid.AutoRotate = false
	-- JumpPower/JumpHeight 둘 다 0 (UseJumpPower 설정과 무관하게 점프 차단)
	pcall(function() humanoid.JumpPower = 0 end)
	pcall(function() humanoid.JumpHeight = 0 end)
end

-- 접속 처리
local function onPlayerAdded(player)
	playerConns[player] = {}
	local slot = takeSlot(player)

	-- 캐릭터 고정 먼저 연결 (로드가 느려도 캐릭터는 바로 고정되게.
	--  리스폰 시에도 CharacterAdded가 다시 고정해 줘요)
	table.insert(playerConns[player], player.CharacterAdded:Connect(function(character)
		task.defer(pinCharacter, player, character, slot)
	end))
	if player.Character then
		task.defer(pinCharacter, player, player.Character, slot)
	end

	-- 저장 데이터 로드 (pcall 재시도 포함) → 경제 세팅
	local data = SaveData.Load(player)
	if not player.Parent then
		return  -- 로드하는 사이 퇴장함
	end
	Economy.AddPlayer(player, data)

	-- 첫 접속자의 최고 스테이지로 건물 재설정 (현재 스테이지보다 높을 때만, 서버당 1회)
	if not firstPlayerApplied then
		firstPlayerApplied = true
		local best = data.bestStage or 1
		if best > Building.GetStage() and Building.GetState() == "전투" then
			Combat.ResetHitters()  -- 교체 전 건물을 때린 기록은 무효 (보너스 공짜 수령 방지)
			local newMax = Building.BuildStage(best)
			-- 전원에게 새 건물 상태 알림 (이미 접속한 클라의 화면·카메라도 맞춰줘요)
			Remotes.Stage:FireAllClients("new", best, newMax, newMax, 0)
		end
	end

	-- 늦은 입장자 동기화: 그 클라에만 현재 상태 1회
	local hp, maxHp = Building.GetHP()
	Remotes.Stage:FireClient(player, "sync", Building.GetStage(), hp, maxHp, 0)
end

-- 퇴장 처리
local function onPlayerRemoving(player)
	SaveData.Save(player)
	Economy.RemovePlayer(player)
	releaseSlot(player)
	local conns = playerConns[player]
	if conns then
		for _, c in ipairs(conns) do
			pcall(function() c:Disconnect() end)
		end
		playerConns[player] = nil
	end
end

Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(onPlayerRemoving)

-- 이미 접속해 있던 플레이어 처리 (스크립트가 늦게 켜진 경우)
for _, p in ipairs(Players:GetPlayers()) do
	task.spawn(onPlayerAdded, p)
end

-- 자동저장 시작
SaveData.StartAutoSave()

print("[건물부수기] 서버 준비 완료! 클릭 연타로 건물을 부수세요!")
