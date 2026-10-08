-- 월드 만들기 (서버)
-- 빈 Baseplate에서도 바로 놀 수 있게 땅·보도·배경·받침대·조명을 전부 코드로 만들어요.
-- 충돌그룹("잔해"-"플레이어" 끄기)도 여기서 설정해요.

local Lighting = game:GetService("Lighting")
local PhysicsService = game:GetService("PhysicsService")
local Workspace = game:GetService("Workspace")

local World = {}

-- 파트 만들기 도우미 (속성 다 정하고 마지막에 Parent)
local function makePart(props, parent)
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = true
	p.CanTouch = false
	p.CanQuery = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	for k, v in pairs(props) do
		p[k] = v
	end
	p.Parent = parent
	return p
end

-- 받침대 슬롯 위치 (slot 0~7)
function World.PadPosition(slot)
	return Vector3.new(-20, 2.5, 20 + slot * 5)
end

function World.Build()
	-- 충돌그룹: 잔해끼리/기본과는 충돌, 잔해-플레이어는 비충돌
	pcall(function()
		PhysicsService:RegisterCollisionGroup("잔해")
		PhysicsService:RegisterCollisionGroup("플레이어")
		PhysicsService:CollisionGroupSetCollidable("잔해", "플레이어", false)
		PhysicsService:CollisionGroupSetCollidable("잔해", "잔해", true)
		PhysicsService:CollisionGroupSetCollidable("잔해", "Default", true)
	end)

	-- 템플릿의 기본 Baseplate 제거 (우리 바닥과 윗면이 같은 y=0 평면이라
	--  그대로 두면 잔디면과 겹쳐 깜빡여요 — z-fighting 방지)
	local bp = Workspace:FindFirstChild("Baseplate")
	if bp and bp:IsA("BasePart") then
		bp:Destroy()
	end

	local folder = Instance.new("Folder")
	folder.Name = "월드"

	-- 바닥 (윗면이 Y=0)
	makePart({
		Name = "바닥",
		Size = Vector3.new(200, 2, 120),
		CFrame = CFrame.new(0, -1, 0),
		Color = Color3.fromRGB(106, 158, 86),
		Material = Enum.Material.Grass,
	}, folder)

	-- 보도 (건물 앞쪽 회색 길)
	makePart({
		Name = "보도",
		Size = Vector3.new(200, 0.4, 18),
		CFrame = CFrame.new(0, 0.2, 14),
		Color = Color3.fromRGB(180, 180, 180),
		Material = Enum.Material.Concrete,
	}, folder)

	-- 하늘색 배경벽 (건물 뒤, 카메라 반대쪽)
	makePart({
		Name = "배경벽",
		Size = Vector3.new(400, 160, 2),
		CFrame = CFrame.new(0, 60, -60),
		Color = Color3.fromRGB(150, 205, 245),
		Material = Enum.Material.SmoothPlastic,
		CanCollide = false,
	}, folder)

	-- 구름 파트들 (하얀 네모 몇 개)
	local clouds = {
		{Vector3.new(-60, 48, -56), Vector3.new(26, 7, 2)},
		{Vector3.new(-38, 54, -56), Vector3.new(16, 5, 2)},
		{Vector3.new(30, 60, -56), Vector3.new(30, 8, 2)},
		{Vector3.new(55, 52, -56), Vector3.new(18, 5, 2)},
		{Vector3.new(0, 72, -56), Vector3.new(22, 6, 2)},
	}
	for i, info in ipairs(clouds) do
		makePart({
			Name = "구름" .. i,
			Size = info[2],
			CFrame = CFrame.new(info[1]),
			Color = Color3.fromRGB(255, 255, 255),
			Material = Enum.Material.SmoothPlastic,
			CanCollide = false,
		}, folder)
	end

	-- 받침대 8개 (플레이어가 서는 곳)
	for slot = 0, 7 do
		local pos = World.PadPosition(slot)
		makePart({
			Name = "받침대" .. slot,
			Size = Vector3.new(4, 1, 4),
			CFrame = CFrame.new(pos.X, 0.5, pos.Z),
			Color = Color3.fromRGB(230, 220, 120),
			Material = Enum.Material.WoodPlanks,
		}, folder)
	end

	folder.Parent = Workspace

	-- 조명: 밝은 한낮
	Lighting.ClockTime = 14
	Lighting.Brightness = 2
	Lighting.GlobalShadows = true

	return folder
end

return World
