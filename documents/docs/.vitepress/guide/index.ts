import { getMdFilesAsync } from "../utils";
import path from 'path';
import { DefaultTheme } from 'vitepress';

export function getGuideSideBarItems(): (DefaultTheme.SidebarItem)[] {
  return getMdFilesAsync(path.resolve(__dirname, '../../guide'))
  .map(item => {
    return {
      text: item,
      link: `/${item}`
    }
  })
}
