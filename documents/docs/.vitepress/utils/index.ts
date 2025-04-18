import fs from 'fs-extra';
import path from 'path';

export function getMdFilesAsync(rootDir: string) {
    const results: string[] = [];
    
    function traverse(currentDir) {
        const entries =  fs.readdirSync(currentDir, { withFileTypes: true });
        
        entries.map(async (entry) => {
          const entryPath = path.join(currentDir, entry.name);
          
          if (entry.isDirectory()) {
              traverse(entryPath); // 递归子目录[3](@ref)
          } else if (path.extname(entry.name).toLowerCase() === '.md') {
              const relativePath = path.relative(rootDir, entryPath);
              results.push(relativePath);
          }
      })
    }
    
    traverse(rootDir);
    return results.map(item => {
      return item.replace('.md', '');
    });
}
