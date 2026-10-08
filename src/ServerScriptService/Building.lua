-- 건물 (서버)
-- 블록을 층층이 쌓아 건물을 만들고, HP를 관리하고,
-- 부서지는 단계(2/3, 1/3)와 붕괴(와르르!)까지 전부 담당해요.

local Debris = game:GetService("Debris")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage:WaitForChild("Game"):WaitForChild("Config"))

local Building = {}

-- 내부 상태
local state = "전투"        -- "전투" 또는 "붕괴중"
local stage = 1
local hp = 0
local maxHp = 0
local blocks = {}           -- 살아있는 블록 파트 배열 (지붕 포함)
local model = nil
local passedThresholds = {} -- 이미 지난 파손 문턱

-- 창문 SurfaceGui 만들기 (전면 블록용)
-- 점등 패턴은 Random.new(시드)로 서버·클라 동일 산출
local function attachWindows(block, seed)
	local rng = Random.new(seed)
	local gui = Instance.new("SurfaceGui")
	gui.Name = "창문"
	gui.Face = Enum.NormalId.Back  -- 무회전 파트의 +Z면. 카메라가 +Z에 있어서 이 면이 보여요
	gui.CanvasSize = Vector2.new(400, 200)
	gui.LightInfluence = 0
	for i = 1, 3 do
		local lit = rng:NextNumber() < 0.55  -- 켜진 창 / 꺼진 창
		local win = Instance.new("Frame")
		win.Name = "창" .. i
		win.Size = UDim2.fromOffset(80, 100)
		win.Position = UDim2.fromOffset(30 + (i - 1) * 130, 50)
		win.BorderSizePixel = 0
		win.BackgroundColor3 = lit and Color3.fromRGB(255, 230, 140) or Color3.fromRGB(44, 50, 66)
		local corner = Instance.new("UICorner")
		corner.CornerRadius = UDim.new(0, 8)
		corner.Parent = win
		win.Parent = gui
	end
	gui.Parent = block
end

-- 블록 하나 만들기
local function makeBlock(name, size, cframe, color)
	local b = Instance.new("Part")
	b.Name = name
	b.Size = size
	b.CFrame = cframe
	b.Color = color
	b.Material = Enum.Material.Concrete
	b.Anchored = true
	b.CanCollide = true
	b.CanTouch = false
	b.CanQuery = false
	b.TopSurface = Enum.SurfaceType.Smooth
	b.BottomSurface = Enum.SurfaceType.Smooth
	b.CollisionGroup = "잔해"
	return b
end

-- 스테이지 s의 건물 짓기 (완성형·불투명 — 등장 연출은 클라 몫)
function Building.BuildStage(s)
	stage = s
	maxHp = Config.buildingHP(s)
	hp = maxHp
	passedThresholds = {}
	blocks = {}

	-- 이전 모델 정리
	if model then
		model:Destroy()
		model = nil
	end

	local palette = Config.palettes[(s - 1) % #Config.palettes + 1]
	local wallColor, roofColor = palette[1], palette[2]
	local floors = Config.floorCount(s)
	local size = Config.building.blockSize  -- (12, 6, 7)

	local m = Instance.new("Model")
	m.Name = "건물"
	m:SetAttribute("Stage", s)  -- 클라가 "지금 스테이지 건물"인지 확인하는 표식

	-- 층 k(1부터)의 블록 중심 y = k*6 - 3. 층당 2x2 = 4블록 (x=±6, z=±3.5)
	for k = 1, floors do
		local y = k * Config.building.floorHeight - 3
		local idx = 0
		for _, x in ipairs({-6, 6}) do
			for _, z in ipairs({-3.5, 3.5}) do
				idx += 1
				local b = makeBlock(
					string.format("층%d_블록%d", k, idx),
					size,
					CFrame.new(x, y, z),
					wallColor
				)
				if z > 0 then
					attachWindows(b, s * 1000 + k * 10 + idx)  -- 전면 블록에만 창문
				end
				b.Parent = m
				table.insert(blocks, b)
			end
		end
	end

	-- 지붕
	local roof = makeBlock(
		"지붕",
		Config.building.roofSize,
		CFrame.new(0, floors * Config.building.floorHeight + 0.5, 0),
		roofColor
	)
	roof.Parent = m
	table.insert(blocks, roof)

	m.Parent = Workspace
	model = m
	state = "전투"

	return maxHp
end

-- 타격점 산출 (전원 같은 위치에 연출이 보이게 서버가 정함)
function Building.GetHitPos()
	local floors = Config.floorCount(stage)
	local topY = math.max(1, floors * Config.building.floorHeight - 1)
	return Vector3.new(
		math.random(-10, 10),
		math.random(1, topY),
		Config.building.depth / 2  -- 전면 z = 7
	)
end

-- 파손 문턱 지속 연출: 무작위 30% 블록 어둡게 + Slate + ±3° 기울임 (서버라 복제 공짜)
local function crackBuilding()
	for _, b in ipairs(blocks) do
		if b.Parent and b.Name ~= "지붕" and math.random() < 0.3 then
			local c = b.Color
			b.Color = Color3.new(c.R * 0.6, c.G * 0.6, c.B * 0.6)
			b.Material = Enum.Material.Slate
			local angle = math.rad(math.random(-3, 3))
			b.CFrame = b.CFrame * CFrame.Angles(0, 0, angle)
		end
	end
end

-- 데미지 적용 → 남은 HP 반환. 파손 문턱 통과 처리도 여기서.
function Building.ApplyDamage(damage)
	if state ~= "전투" then
		return hp
	end
	hp = math.max(0, hp - damage)

	local ratio = hp / maxHp
	for i, threshold in ipairs(Config.damageThresholds) do
		if ratio <= threshold and not passedThresholds[i] then
			passedThresholds[i] = true
			crackBuilding()
		end
	end

	return hp
end

-- 붕괴 물리: 전 블록 언앵커 + 임펄스 + 서버 소유권 + Debris
function Building.StartCollapse()
	state = "붕괴중"
	local baseCenter = Vector3.new(0, 0, 0)
	for _, b in ipairs(blocks) do
		if b.Parent then
			b.Anchored = false
			b.CanCollide = true
			pcall(function()
				b:SetNetworkOwner(nil)  -- 서버가 물리 계산 → 전원 같은 화면
			end)
			local dir = b.Position - baseCenter
			if dir.Magnitude < 0.01 then
				dir = Vector3.new(0, 1, 0)
			end
			b.AssemblyLinearVelocity = dir.Unit * math.random(16, 40)
				+ Vector3.new(0, math.random(24, 52), 0)
			b.AssemblyAngularVelocity = Vector3.new(
				(math.random() * 2 - 1) * 8,
				(math.random() * 2 - 1) * 8,
				(math.random() * 2 - 1) * 8
			)
			Debris:AddItem(b, Config.collapse.debrisLife)
		end
	end
	blocks = {}  -- 즉시 비움 (잔해는 Debris가 치움)
end

-- 읽기·쓰기 접근자들
function Building.GetState()
	return state
end
function Building.SetState(s)
	state = s
end
function Building.GetStage()
	return stage
end
function Building.GetHP()
	return hp, maxHp
end

return Building
