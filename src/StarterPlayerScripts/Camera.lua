-- 카메라 (클라)
-- 2D 게임처럼 보이는 측면 고정 카메라예요. 건물 높이에 맞춰 자동으로 줌아웃하고,
-- 타격 때마다 Shake(세기)로 화면을 흔들어요.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local GameFolder = ReplicatedStorage:WaitForChild("Game")
local Config = require(GameFolder:WaitForChild("Config"))

local CameraMod = {}

local connections = {}
local shakeMag = 0          -- 현재 셰이크 세기
local currentPos = nil      -- 지수 보간용 현재 카메라 위치
local currentLook = nil
local buildingHeight = 4 * Config.building.floorHeight  -- 기본: 스테이지1 = 4층

-- 외부(Fx·Main)에서 호출: 셰이크는 max 누적
function CameraMod.Shake(mag)
	shakeMag = math.max(shakeMag, mag)
end

-- 스테이지 바뀔 때 호출 (건물 높이 갱신 → 목표 줌 자동 변화)
function CameraMod.SetStage(s)
	buildingHeight = Config.floorCount(s) * Config.building.floorHeight
end

function CameraMod.Init()
	local camera = Workspace.CurrentCamera
	camera.CameraType = Enum.CameraType.Scriptable
	camera.FieldOfView = Config.camera.FOV

	-- 탈취 감시: 다른 스크립트가 CameraType을 바꾸면 다시 강제
	-- (매 프레임 체크 대신 PropertyChangedSignal 사용)
	table.insert(connections, camera:GetPropertyChangedSignal("CameraType"):Connect(function()
		if camera.CameraType ~= Enum.CameraType.Scriptable then
			camera.CameraType = Enum.CameraType.Scriptable
		end
	end))
	-- CurrentCamera 자체가 교체될 수도 있음
	table.insert(connections, Workspace:GetPropertyChangedSignal("CurrentCamera"):Connect(function()
		local newCamera = Workspace.CurrentCamera
		if newCamera and newCamera ~= camera then
			camera = newCamera
			camera.CameraType = Enum.CameraType.Scriptable
			camera.FieldOfView = Config.camera.FOV
		end
	end))

	-- 매 프레임: 목표 위치로 지수 보간 + 셰이크
	table.insert(connections, RunService.RenderStepped:Connect(function(dt)
		local Hb = buildingHeight
		local targetPos = Vector3.new(0, Config.cameraY(Hb), Config.cameraZ(Hb))
		local targetLook = Vector3.new(0, Hb * 0.42, 0)

		if not currentPos then
			currentPos = targetPos
			currentLook = targetLook
		end

		-- 지수 보간 추적 (프레임레이트와 무관하게 같은 속도)
		local alpha = 1 - 0.0005 ^ dt
		currentPos = currentPos:Lerp(targetPos, alpha)
		currentLook = currentLook:Lerp(targetLook, alpha)

		-- 셰이크: random 오프셋, 감쇠 0.88^(dt*60)
		local offset = Vector3.zero
		if shakeMag > 0.01 then
			offset = Vector3.new(
				(math.random() * 2 - 1) * shakeMag,
				(math.random() * 2 - 1) * shakeMag,
				0
			)
			shakeMag *= 0.88 ^ (dt * 60)
		else
			shakeMag = 0
		end

		camera.CFrame = CFrame.lookAt(currentPos + offset, currentLook + offset)
	end))
end

return CameraMod
