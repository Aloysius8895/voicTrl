// voicTrl watch viewer. Bundled into ../viewer.bundle.js (npm run build) so index.html
// opens by double-click, offline. The model arrives as base64 in window.WATCH_GLB_BASE64.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const ORANGE = "#ff5a1f";
const MM = 0.001;

// What each part is, by object-name prefix (longest match wins). Same names as blender/spec.md.
const PART_INFO = [
  ["SM_glass_ink", "玻璃黑边", "印在玻璃背面的一圈油墨"],
  ["SM_glass", "盖板玻璃", "43.3 mm 见方，厚 0.7 mm"],
  ["SM_display_screen", "屏幕显示区", "38.39 mm 见方；声波是概念界面"],
  ["SM_display", "屏幕模组", "2.16 寸 AMOLED，480 × 480"],
  ["SM_case", "白色外壳", "46 × 46 × 12 mm"],
  ["SM_btn_function", "功能键", "橙色的 AI 键，戴在手上时朝手掌"],
  ["SM_btn_power", "POWER 键", "单击开关机"],
  ["SM_btn_boot", "BOOT 键", "上电时按住进入下载模式"],
  ["SM_label", "引脚标签", "排母旁的贴纸，橙色格是电源脚"],
  ["SM_core_pcb", "CoreBoard", "主板：芯片、屏幕、按键、USB-C 都在这块板上"],
  ["SM_core_ics_front", "主板芯片", "ESP32-S31、Flash、PSRAM、IMU 等"],
  ["SM_core_antenna_led", "陶瓷天线和充电灯", "天线靠功能键一边，充电灯靠 USB-C"],
  ["SM_core_display_conn", "屏幕排线座", ""],
  ["SM_core_switch_plungers", "按键开关的按柄", ""],
  ["SM_core_switches_mic", "按键开关和麦克风", "三个侧按开关，加一颗 MEMS 麦克风"],
  ["SM_core_usbc", "USB-C 母座", "供电、下载固件、充电"],
  ["SM_core_btb_plug", "板对板连接器（公）", "60 针，0.5 mm 间距"],
  ["SM_core_motor", "震动马达", ""],
  ["SM_core_gold", "测试点和焊盘环", ""],
  ["SM_core_passives", "贴片阻容", "分布是示意，不是真实布局"],
  ["SM_base_pcb", "BaseBoard", "底板，它的背面就是手表的背面"],
  ["SM_base_speaker", "扬声器", "对着外壳上的 6 条斜孔"],
  ["SM_base_btb", "板对板连接器（母）", "60 针，0.5 mm 间距"],
  ["SM_base_battery", "电池", "501220 锂电池，3.7 V 65 mAh"],
  ["SM_base_header_pins", "排母针脚", ""],
  ["SM_base_header", "扩展排母", "2 × 10，2.54 mm 间距，两侧各一个"],
  ["SM_base_connectors", "电池和扬声器插座", ""],
  ["SM_base_ics", "稳压芯片", "TLV62569"],
  ["SM_base_edge_parts", "板边小件", ""],
  ["SM_base_gold", "背面扩展焊盘", "GND BOOT RST RX TX 5V GND"],
  ["SM_base_marks", "背面标志和文字", "照官方产品背面照片做的"],
  ["SM_standoffs", "铜柱", "撑开两块板，螺丝从中间穿过"],
  ["SM_screw", "螺丝", "四颗，从背面拧入外壳"],
  ["SM_cradle", "托架", "我们设计的 3D 打印件"],
  ["SM_strap_keeper", "带环", ""],
  ["SM_strap", "尼龙表带", "22 mm 宽，内圈 165 mm"],
  ["SM_buckle", "滑扣", ""],
].sort((a, b) => b[0].length - a[0].length);

const api = { ready: false, parts: () => [], offsetMm: () => null, isShown: () => false };
window.watchViewer = api;

const stage = document.querySelector("#stage");
const status = document.querySelector("#status");

function fail(message) {
  status.textContent = message;
  status.hidden = false;
}

// Blender axes (x, y, z-up) to three.js axes (x, y-up, z): the glTF exporter's conversion.
const fromBlender = (x, y, z) => new THREE.Vector3(x, z, -y);

function makeRenderer() {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.NeutralToneMapping; // Khronos PBR Neutral, as in the Blender renders
  stage.appendChild(renderer.domElement);
  return renderer;
}

// Studio light for reflections, the same idea as the Blender set: a softbox, two strips and a dim
// dome, with nothing bright straight above the screen, so the glass stays black when seen head-on.
function makeStudio(renderer) {
  const studio = new THREE.Scene();
  const panel = (w, h, level, x, y, z) => {
    const mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(w, h),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(level, level, level), side: THREE.DoubleSide }),
    );
    mesh.position.set(x, y, z);
    mesh.lookAt(0, 0, 0);
    studio.add(mesh);
  };
  studio.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(6, 32, 16),
      new THREE.MeshBasicMaterial({ color: new THREE.Color(0.16, 0.16, 0.16), side: THREE.BackSide }),
    ),
  );
  panel(1.6, 1.6, 7, -1.6, 1.3, 1.6); // softbox, upper left front
  panel(0.25, 2.6, 9, 2.2, 0.5, -0.9); // strip, right rear
  panel(0.25, 2.6, 6, -2.3, 0.2, -1.4); // strip, left rear
  panel(2.4, 0.5, 3, 0.4, -1.6, 1.2); // low fill, so the underside is not black
  const pmrem = new THREE.PMREMGenerator(renderer);
  const texture = pmrem.fromScene(studio, 0.03).texture;
  pmrem.dispose();
  studio.traverse((node) => {
    node.geometry?.dispose();
    node.material?.dispose();
  });
  return texture;
}

// The screen: black, with the orange voice waveform redrawn every frame.
function makeWaveform() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 512;
  const ctx = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.flipY = false; // matches the UVs GLTFLoader gives the screen
  const bars = 12;
  const cell = 0.6 / bars; // the bars cover u = 0.2 .. 0.8, the same layout as the Blender shader
  const radius = cell * 0.3;
  function draw(phase) {
    const size = canvas.width;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = ORANGE;
    for (let i = 0; i < bars; i++) {
      const wobble = Math.abs(0.5 * Math.sin(1.9 * i + phase) + 0.5 * Math.sin(0.83 * i + 1.3));
      const half = 0.03 + wobble * Math.sin((Math.PI * (i + 0.5)) / bars) * 0.2;
      const u = 0.2 + (i + 0.5) * cell;
      ctx.beginPath();
      ctx.roundRect((u - radius) * size, (0.5 - half) * size, 2 * radius * size, 2 * half * size, radius * size);
      ctx.fill();
    }
    texture.needsUpdate = true;
  }
  const material = new THREE.MeshStandardMaterial({
    color: 0x040405,
    roughness: 0.15,
    emissive: 0xffffff,
    emissiveMap: texture,
    emissiveIntensity: 1.5,
  });
  return { material, draw };
}

// Nylon webbing: a small tiling height map. The strap's UVs are in millimetres.
function makeWeave() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(64, 64);
  for (let y = 0; y < 64; y++) {
    for (let x = 0; x < 64; x++) {
      const rib = Math.sin((2 * Math.PI * (x + y)) / 32) * Math.sin((2 * Math.PI * (x - y)) / 64);
      const v = Math.round(128 + 110 * rib);
      image.data.set([v, v, v, 255], (y * 64 + x) * 4);
    }
  }
  ctx.putImageData(image, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1 / 2.8, 1 / 2.8); // one tile every 2.8 mm
  return texture;
}

async function loadWatch() {
  const base64 = window.WATCH_GLB_BASE64;
  if (!base64) throw new Error("watch.glb.js is missing: run blender/export_web.py");
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const gltf = await new GLTFLoader().parseAsync(bytes.buffer, "");
  return gltf.scene;
}

async function main() {
  let renderer;
  try {
    renderer = makeRenderer();
  } catch {
    fail("这个浏览器打不开 WebGL，换 Chrome 或 Edge 试试。");
    return;
  }
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0b0c);
  scene.environment = makeStudio(renderer);
  const key = new THREE.DirectionalLight(0xffffff, 2.0);
  key.position.copy(fromBlender(-0.3, -0.5, 0.8));
  scene.add(key);
  const under = new THREE.DirectionalLight(0xffffff, 1.3); // so the back reads when the watch is turned over
  under.position.copy(fromBlender(0.3, 0.4, -0.8));
  scene.add(under);

  const camera = new THREE.PerspectiveCamera(28, 1, 0.01, 5);
  const target = fromBlender(0, 0, -16 * MM);
  camera.position.copy(fromBlender(0.115, -0.142, 0.154)).add(target);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(target);
  controls.enableDamping = true;
  controls.minDistance = 0.08;
  controls.maxDistance = 1.2;

  const watch = await loadWatch();
  scene.add(watch);
  const waveform = makeWaveform();
  const weave = makeWeave();
  const parts = [];
  watch.traverse((node) => {
    if (!node.isMesh) return;
    parts.push(node);
    if (node.name === "SM_display_screen") node.material = waveform.material;
    if (node.name === "SM_strap") {
      node.material.bumpMap = weave;
      node.material.bumpScale = 1.5;
      node.material.sheen = 0; // the exported sheen washes the orange out to pink here
    }
    if (node.name === "SM_glass") node.material.side = THREE.FrontSide;
  });
  api.parts = () => parts.map((part) => part.name);

  // ---- explode: every node that carries explode_mm slides along it; children ride on their parent
  const movers = [];
  const home = new Map();
  watch.updateMatrixWorld(true);
  watch.traverse((node) => {
    home.set(node.name, node.getWorldPosition(new THREE.Vector3()));
    const mm = node.userData.explode_mm;
    if (mm) movers.push({ node, rest: node.position.clone(), step: fromBlender(...mm).multiplyScalar(MM) });
  });
  const slider = document.querySelector("#explode");
  const reach = (amount) => 1 + 1.15 * amount; // how far the camera backs off to keep everything in view
  let exploded = 0;
  function explode(amount) {
    for (const { node, rest, step } of movers) node.position.copy(rest).addScaledVector(step, amount);
    const centre = fromBlender(0, 0, THREE.MathUtils.lerp(-16, -34, amount) * MM);
    const offset = camera.position.clone().sub(controls.target).multiplyScalar(reach(amount) / reach(exploded));
    controls.target.copy(centre);
    camera.position.copy(centre).add(offset);
    controls.maxDistance = 1.2 * reach(amount);
    exploded = amount;
  }
  slider.addEventListener("input", () => explode(Number(slider.value)));
  api.offsetMm = (name) => {
    const node = watch.getObjectByName(name);
    if (!node) return null;
    watch.updateMatrixWorld(true);
    const d = node.getWorldPosition(new THREE.Vector3()).sub(home.get(name)).divideScalar(MM);
    return [d.x, -d.z, d.y]; // back to the model's axes
  };

  // ---- our own parts (cradle, strap and what hangs on it) can be hidden to see the bare module
  const isShown = (node) => {
    for (let n = node; n; n = n.parent) if (!n.visible) return false;
    return true;
  };
  api.isShown = (name) => {
    const node = watch.getObjectByName(name);
    return node ? isShown(node) : false;
  };
  const wearable = document.querySelector("#wearable");
  wearable.addEventListener("change", () => {
    for (const name of ["SM_cradle", "SM_strap"]) watch.getObjectByName(name).visible = wearable.checked;
    pick(null);
  });

  // ---- click a part to see what it is; a drag (orbiting) does not count as a click
  const card = document.querySelector("#part");
  const raycaster = new THREE.Raycaster();
  let picked = null;
  function pick(part) {
    if (picked) picked.node.material = picked.material;
    picked = null;
    card.hidden = !part;
    if (!part) return;
    const [, title, note] = PART_INFO.find(([prefix]) => part.name.startsWith(prefix)) ?? ["", part.name, ""];
    document.querySelector("#part-name").textContent = title;
    document.querySelector("#part-id").textContent = part.name;
    document.querySelector("#part-note").textContent = note;
    picked = { node: part, material: part.material };
    if (!part.material.emissiveMap) {
      part.material = part.material.clone(); // tint this part only: materials are shared between parts
      part.material.emissive.set(ORANGE);
      part.material.emissiveIntensity = part.material.transmission ? 0.1 : 0.3;
    }
  }
  let down = null;
  renderer.domElement.addEventListener("pointerdown", (event) => (down = [event.clientX, event.clientY]));
  renderer.domElement.addEventListener("pointerup", (event) => {
    if (!down || Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 5) return;
    const rect = renderer.domElement.getBoundingClientRect();
    const pointer = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    raycaster.setFromCamera(pointer, camera);
    pick(raycaster.intersectObjects(parts.filter(isShown), false)[0]?.object ?? null); // the raycaster ignores visibility
  });

  function resize() {
    const { clientWidth: width, clientHeight: height } = stage;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();

  const timer = new THREE.Timer();
  timer.connect(document);
  let phase = 0;
  renderer.setAnimationLoop(() => {
    timer.update();
    const dt = timer.getDelta();
    phase += dt * 2.4;
    waveform.draw(phase);
    controls.update(dt);
    renderer.render(scene, camera);
  });
  status.hidden = true;
  api.ready = true;
}

main().catch((error) => {
  console.error(error);
  fail("模型没能加载：" + error.message);
});
