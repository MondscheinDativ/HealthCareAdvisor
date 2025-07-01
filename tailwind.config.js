module.exports = {
  content: ["./src/**/*.{js,jsx,html}"], // 扫描 src 下所有 JS/JSX/HTML 文件
  theme: {
    extend: {
      colors: {
        legal: '#8B0000', // 法律声明模块红色
        notice: '#FFA500', // 提示模块橙色
      },
      fontFamily: {
        sans: ['"Microsoft YaHei"', 'Arial', 'sans-serif'], // 统一中文字体
      },
    },
  },
  plugins: [],
}
