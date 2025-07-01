import React from 'react';
import { Link } from 'react-router-dom';

const LegalNotice = () => (
  <div className="bg-legal/5 border-t-4 border-legal text-legal p-4">
    <p className="text-sm text-center">
      本内容仅供参考，不构成医疗建议！<Link to="/legal" className="underline">完整声明</Link>
    </p>
  </div>
);

export default LegalNotice;
