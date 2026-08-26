# Garment extraction acceptance fixtures

These synthetic, privacy-safe fixtures were generated with OpenAI's built-in
image generation tool on 2026-08-26. They depict the same plain cobalt-blue
upper garment in the four input modes required by issue #2:

- `worn-person.jpg`: a fictional adult wearing the shirt;
- `mannequin.jpg`: the shirt on a neutral retail mannequin;
- `hanger.jpg`: the shirt on a wooden hanger;
- `flat-lay.jpg`: a top-down flat-lay shirt.

The prompts requested photorealistic catalog photographs, an uncluttered light
gray background, one clearly visible blue T-shirt, and no logos, text,
watermarks, accessories, or additional garments. Images were resized to fit
within 768x768 and encoded as JPEG quality 82 for repository use.

The blue garment is deliberate: the model-level acceptance test can detect
semantic leakage by measuring how much non-blue person, mannequin, hanger, or
background remains in the returned foreground.
