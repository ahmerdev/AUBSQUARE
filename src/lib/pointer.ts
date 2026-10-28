/** Normalised (-1..1) fine-pointer position shared by 3D scenes. Touch input is ignored on purpose. */
export const pointer = { x: 0, y: 0, active: false };

let bound = false;
export const bindPointer = () => {
  if (bound || typeof window === 'undefined') return;
  bound = true;
  window.addEventListener(
    'pointermove',
    (e) => {
      if (e.pointerType === 'touch') return;
      pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.y = -((e.clientY / window.innerHeight) * 2 - 1);
      pointer.active = true;
    },
    { passive: true }
  );
};
