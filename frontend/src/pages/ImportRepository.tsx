import React from "react";
import { RepositoryImport } from "../components/RepositoryImport";

interface ImportRepositoryPageProps {
  onSelectRepo: (repoId: number) => void;
}

export const ImportRepository: React.FC<ImportRepositoryPageProps> = ({ onSelectRepo }) => {
  return (
    <div className="page-container">
      <RepositoryImport onSelectRepo={onSelectRepo} />
    </div>
  );
};
