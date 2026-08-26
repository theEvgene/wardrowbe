# Garment extraction acceptance fixtures

These synthetic, privacy-safe fixtures were generated with OpenAI's built-in
image generation tool on 2026-08-26. They depict the same plain cobalt-blue
upper garment in the four input modes required by issue #2:

- `worn-person.jpg`: a fictional adult wearing the shirt;
- `mannequin.jpg`: the shirt on a neutral retail mannequin;
- `hanger.jpg`: the shirt on a wooden hanger;
- `flat-lay.jpg`: a top-down flat-lay shirt.

Issue #9 extends the matrix with three harder generated inputs:

- `worn-upper-occluded.jpg`: a fictional adult crossing bare forearms over a
  cobalt-blue T-shirt, testing moderate foreground occlusion;
- `worn-lower-pants.jpg`: a fictional adult wearing cobalt-blue trousers with
  a neutral top and shoes, testing the lower-body segmentation class;
- `worn-full-dress.jpg`: a fictional adult wearing a plain cobalt-blue dress,
  testing the full-body segmentation class.

The prompts requested photorealistic catalog photographs, an uncluttered light
gray background, one clearly visible blue T-shirt, and no logos, text,
watermarks, accessories, or additional garments. Images were resized to fit
within 768x768 and encoded as JPEG quality 82 for repository use.

The blue garment is deliberate: the model-level acceptance test can detect
semantic leakage by measuring how much non-blue person, mannequin, hanger, or
background remains in the returned foreground.

The issue #9 prompts used the same photorealistic catalog constraints and made
the selected garment the only blue object. Respectively, they requested blue
trousers with a gray top and white shoes, a blue short-sleeve dress with neutral
shoes, and a blue T-shirt moderately occluded by crossed bare forearms. Every
prompt excluded brands, logos, text, watermarks, accessories, and additional
people. These images were generated with the built-in ImageGen tool on
2026-08-26 and processed with the same 768px/JPEG settings as the original set.
