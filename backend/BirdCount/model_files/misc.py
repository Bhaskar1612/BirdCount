import torch
import math
inf = math.inf

from torchvision import transforms


def make_grid(imgs, h, w):
    assert len(imgs) == 9
    rows = []
    for i in range(0, 9, 3):
        row = torch.cat((imgs[i], imgs[i + 1], imgs[i + 2]), -1)
        rows += [row]
    grid = torch.cat((rows[0], rows[1], rows[2]), 0)
    grid = transforms.Resize((h, w))(grid.unsqueeze(0))
    return grid.squeeze(0)













